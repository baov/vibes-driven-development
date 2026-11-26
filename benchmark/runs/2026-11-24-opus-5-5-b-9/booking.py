"""Seat booking for cinema screenings, with cancellation and refund.

Refunds go through a payment gateway supplied by the caller. The gateway
must expose ``refund(booking_id, amount)`` and signal failures by raising
one of the three gateway exceptions defined below.
"""

import enum
import itertools
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

CANCELLATION_DEADLINE = timedelta(hours=2)
REFUND_RETRIES = 3


# --- Gateway contract -------------------------------------------------------

class RefundGatewayError(Exception):
    """Base class for errors raised by a payment gateway."""


class TransientRefundError(RefundGatewayError):
    """The refund failed but may succeed if attempted again."""


class PermanentRefundError(RefundGatewayError):
    """The refund was refused and will not succeed if attempted again."""


class GatewayUnavailableError(RefundGatewayError):
    """The gateway cannot be reached; no refund was attempted."""


class PaymentGateway(Protocol):
    def refund(self, booking_id: str, amount: Decimal) -> None:
        """Refund ``amount`` for ``booking_id``.

        ``booking_id`` is stable across retries so the gateway can use it as
        an idempotency key.
        """


# --- Service errors ---------------------------------------------------------

class BookingError(Exception):
    """Base class for rejected booking operations."""


class UnknownScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


class ScreeningAlreadyStartedError(BookingError):
    pass


class UnknownBookingError(BookingError):
    pass


class NotBookingOwnerError(BookingError):
    pass


class BookingAlreadyCancelledError(BookingError):
    pass


class CancellationInProgressError(BookingError):
    pass


class CancellationDeadlinePassedError(BookingError):
    pass


class RefundUnavailableError(BookingError):
    """The gateway was unavailable; the cancellation was rejected."""


class RefundFailedError(BookingError):
    """The refund failed; the booking stays active."""


# --- Model ------------------------------------------------------------------

@dataclass(frozen=True)
class Room:
    name: str
    rows: int
    seats_per_row: int

    def has_seat(self, row: int, seat: int) -> bool:
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    screening_id: str
    starts_at: datetime  # timezone-aware
    room: Room
    price: Decimal


class BookingStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class RefundStatus(enum.Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass
class Booking:
    booking_id: str
    screening_id: str
    client_id: str
    row: int
    seat: int
    amount: Decimal
    status: BookingStatus = BookingStatus.ACTIVE
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --- Service ----------------------------------------------------------------

class BookingService:
    def __init__(
        self,
        gateway: PaymentGateway,
        clock: Callable[[], datetime] = _utc_now,
        refund_retries: int = REFUND_RETRIES,
    ) -> None:
        self._gateway = gateway
        self._clock = clock
        self._refund_retries = refund_retries
        self._screenings: Dict[str, Screening] = {}
        self._bookings: Dict[str, Booking] = {}
        # (screening_id, row, seat) -> booking_id, for active bookings only.
        self._taken_seats: Dict[tuple, str] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def add_screening(self, screening: Screening) -> None:
        with self._lock:
            self._screenings[screening.screening_id] = screening

    def book(self, screening_id: str, client_id: str, row: int, seat: int) -> Booking:
        with self._lock:
            screening = self._screenings.get(screening_id)
            if screening is None:
                raise UnknownScreeningError(screening_id)
            if not screening.room.has_seat(row, seat):
                raise InvalidSeatError(f"row {row}, seat {seat} is not in room {screening.room.name}")
            if self._clock() >= screening.starts_at:
                raise ScreeningAlreadyStartedError(screening_id)
            key = (screening_id, row, seat)
            if key in self._taken_seats:
                raise SeatAlreadyBookedError(f"row {row}, seat {seat} of screening {screening_id}")

            booking = Booking(
                booking_id=f"B{next(self._ids)}",
                screening_id=screening_id,
                client_id=client_id,
                row=row,
                seat=seat,
                amount=screening.price,
            )
            self._bookings[booking.booking_id] = booking
            self._taken_seats[key] = booking.booking_id
            return booking

    def cancel(self, booking_id: str, client_id: str) -> Booking:
        """Cancel a booking and refund it.

        The booking is cancelled only once the refund succeeded. Transient
        gateway failures are retried up to ``refund_retries`` times. A
        permanent failure (or exhausted retries) leaves the booking active
        with refund status FAILED; an unavailable gateway rejects the
        cancellation and leaves the refund status as it was.
        """
        # Validate and claim the booking under the lock, then call the gateway
        # outside it so a slow gateway does not block other operations. The
        # PENDING status prevents a concurrent cancellation of the same booking.
        with self._lock:
            booking = self._bookings.get(booking_id)
            if booking is None:
                raise UnknownBookingError(booking_id)
            if booking.client_id != client_id:
                raise NotBookingOwnerError(booking_id)
            if booking.status is BookingStatus.CANCELLED:
                raise BookingAlreadyCancelledError(booking_id)
            if booking.refund_status is RefundStatus.PENDING:
                raise CancellationInProgressError(booking_id)
            screening = self._screenings[booking.screening_id]
            if self._clock() > screening.starts_at - CANCELLATION_DEADLINE:
                raise CancellationDeadlinePassedError(booking_id)
            previous_refund_status = booking.refund_status
            booking.refund_status = RefundStatus.PENDING

        try:
            self._refund_with_retries(booking)
        except GatewayUnavailableError as exc:
            with self._lock:
                booking.refund_status = previous_refund_status
            logger.warning("Refund gateway unavailable for booking %s", booking_id)
            raise RefundUnavailableError(booking_id) from exc
        except RefundGatewayError as exc:
            with self._lock:
                booking.refund_status = RefundStatus.FAILED
            logger.error("Refund failed for booking %s: %s", booking_id, exc)
            raise RefundFailedError(booking_id) from exc
        except BaseException:
            # Unexpected gateway behaviour: we don't know whether money moved,
            # so record a failure rather than leaving the booking stuck PENDING.
            with self._lock:
                booking.refund_status = RefundStatus.FAILED
            raise

        with self._lock:
            booking.refund_status = RefundStatus.REFUNDED
            booking.status = BookingStatus.CANCELLED
            del self._taken_seats[(booking.screening_id, booking.row, booking.seat)]
        return booking

    def get_refund_status(self, booking_id: str) -> RefundStatus:
        with self._lock:
            booking = self._bookings.get(booking_id)
            if booking is None:
                raise UnknownBookingError(booking_id)
            return booking.refund_status

    def get_booking(self, booking_id: str) -> Optional[Booking]:
        with self._lock:
            return self._bookings.get(booking_id)

    def _refund_with_retries(self, booking: Booking) -> None:
        attempts = 1 + self._refund_retries
        for attempt in range(1, attempts + 1):
            try:
                self._gateway.refund(booking.booking_id, booking.amount)
                return
            except TransientRefundError:
                logger.info(
                    "Transient refund failure for booking %s (attempt %d/%d)",
                    booking.booking_id, attempt, attempts,
                )
                if attempt == attempts:
                    raise
