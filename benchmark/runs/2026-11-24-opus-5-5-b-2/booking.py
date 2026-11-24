"""Seat booking for screenings, with cancellation and refund through a payment gateway."""

from __future__ import annotations

import enum
import itertools
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Protocol

logger = logging.getLogger(__name__)

CANCELLATION_DEADLINE = timedelta(hours=2)
# "Retry up to three times": one initial attempt plus at most three retries.
MAX_REFUND_RETRIES = 3


# --- Errors -----------------------------------------------------------------


class BookingError(Exception):
    """Base class for every rejection raised by the booking manager."""


class SeatNotInRoomError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


class ScreeningAlreadyStartedError(BookingError):
    pass


class BookingNotFoundError(BookingError):
    pass


class BookingAlreadyCancelledError(BookingError):
    pass


class CancellationInProgressError(BookingError):
    pass


class CancellationWindowClosedError(BookingError):
    pass


class RefundFailedError(BookingError):
    """The gateway refused the refund (permanently, or after exhausting retries).

    The booking stays active and its refund status becomes FAILED.
    """


class PaymentGatewayUnavailableError(BookingError):
    """The gateway could not be reached; the cancellation is rejected and nothing changes."""


# Errors a PaymentGateway implementation must raise to signal each failure mode.


class TransientGatewayError(Exception):
    """Temporary failure: the refund may succeed if retried."""


class PermanentGatewayError(Exception):
    """Definitive refusal: retrying will not help."""


class GatewayUnavailableError(Exception):
    """The gateway is down or unreachable."""


class PaymentGateway(Protocol):
    def refund(self, booking_id: str, amount: Decimal) -> None:
        """Refund `amount` for `booking_id`.

        `booking_id` is passed on every attempt so the gateway can use it as an
        idempotency key: a retried call must never refund twice.
        """


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
    id: str
    starts_at: datetime
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
    id: str
    screening: Screening
    client_id: str
    row: int
    seat: int
    status: BookingStatus = BookingStatus.ACTIVE
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# --- Manager ----------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BookingManager:
    """In-memory booking store and the rules for booking and cancelling seats."""

    def __init__(
        self,
        payment_gateway: PaymentGateway,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._gateway = payment_gateway
        self._clock = clock
        self._lock = threading.Lock()
        self._bookings: dict[str, Booking] = {}
        # (screening id, row, seat) -> id of the active booking holding that seat.
        self._taken_seats: dict[tuple[str, int, int], str] = {}
        self._ids = itertools.count(1)

    def book(self, screening: Screening, client_id: str, row: int, seat: int) -> Booking:
        if not screening.room.has_seat(row, seat):
            raise SeatNotInRoomError(
                f"Seat {row}-{seat} does not exist in room {screening.room.name}"
            )
        if self._clock() >= screening.starts_at:
            raise ScreeningAlreadyStartedError(f"Screening {screening.id} has already started")

        seat_key = (screening.id, row, seat)
        with self._lock:
            if seat_key in self._taken_seats:
                raise SeatAlreadyBookedError(
                    f"Seat {row}-{seat} is already booked for screening {screening.id}"
                )
            booking = Booking(
                id=f"B{next(self._ids)}",
                screening=screening,
                client_id=client_id,
                row=row,
                seat=seat,
            )
            self._bookings[booking.id] = booking
            self._taken_seats[seat_key] = booking.id
        return booking

    def cancel(self, booking_id: str) -> Booking:
        # Validate and mark the refund as pending under the lock, so two concurrent
        # cancellations of the same booking cannot both reach the gateway.
        with self._lock:
            booking = self._get(booking_id)
            if booking.status is BookingStatus.CANCELLED:
                raise BookingAlreadyCancelledError(f"Booking {booking_id} is already cancelled")
            if booking.refund_status is RefundStatus.PENDING:
                raise CancellationInProgressError(
                    f"Booking {booking_id} is already being cancelled"
                )
            deadline = booking.screening.starts_at - CANCELLATION_DEADLINE
            if self._clock() > deadline:
                raise CancellationWindowClosedError(
                    f"Booking {booking_id} can only be cancelled until {deadline.isoformat()}"
                )
            previous_refund_status = booking.refund_status
            booking.refund_status = RefundStatus.PENDING

        # The gateway call (with its retries) happens outside the lock.
        try:
            self._refund_with_retries(booking)
        except GatewayUnavailableError as exc:
            with self._lock:
                booking.refund_status = previous_refund_status
            logger.warning("Cancellation of %s rejected: payment gateway unavailable", booking_id)
            raise PaymentGatewayUnavailableError(
                f"Payment gateway unavailable, booking {booking_id} was not cancelled"
            ) from exc
        except (PermanentGatewayError, TransientGatewayError) as exc:
            with self._lock:
                booking.refund_status = RefundStatus.FAILED
            logger.error("Refund for booking %s failed: %r", booking_id, exc)
            raise RefundFailedError(
                f"Refund failed, booking {booking_id} stays active"
            ) from exc

        with self._lock:
            booking.refund_status = RefundStatus.REFUNDED
            booking.status = BookingStatus.CANCELLED
            del self._taken_seats[(booking.screening.id, booking.row, booking.seat)]
        return booking

    def refund_status(self, booking_id: str) -> RefundStatus:
        with self._lock:
            return self._get(booking_id).refund_status

    def get_booking(self, booking_id: str) -> Booking:
        with self._lock:
            return self._get(booking_id)

    def _get(self, booking_id: str) -> Booking:
        try:
            return self._bookings[booking_id]
        except KeyError:
            raise BookingNotFoundError(f"Unknown booking {booking_id}") from None

    def _refund_with_retries(self, booking: Booking) -> None:
        attempt = 0
        while True:
            try:
                self._gateway.refund(booking.id, booking.screening.price)
                return
            except TransientGatewayError as exc:
                if attempt >= MAX_REFUND_RETRIES:
                    raise
                attempt += 1
                logger.info(
                    "Transient refund failure for %s (%r), retry %d/%d",
                    booking.id, exc, attempt, MAX_REFUND_RETRIES,
                )
