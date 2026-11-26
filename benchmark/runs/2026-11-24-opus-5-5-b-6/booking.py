"""Seat booking for screenings, with cancellation and refund through a payment gateway."""

import enum
import itertools
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Dict, Optional, Protocol

CANCELLATION_DEADLINE = timedelta(hours=2)
# A transiently failing refund is retried up to this many times after the first attempt.
MAX_REFUND_RETRIES = 3


# --- Errors -----------------------------------------------------------------

class BookingError(Exception):
    """Base class for every rejection raised by the booking service."""


class ScreeningNotFoundError(BookingError):
    pass


class DuplicateScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


class BookingNotFoundError(BookingError):
    pass


class BookingAlreadyCancelledError(BookingError):
    pass


class CancellationTooLateError(BookingError):
    pass


class RefundFailedError(BookingError):
    """The gateway refused the refund (permanently, or after exhausting retries). The booking stays active."""


class RefundUnavailableError(BookingError):
    """The gateway could not be reached; the cancellation is rejected and nothing was changed."""


# Errors the payment gateway is expected to raise.

class TransientGatewayError(Exception):
    """A temporary failure; the same refund may succeed if retried."""


class PermanentGatewayError(Exception):
    """The refund was definitively refused."""


class GatewayUnavailableError(Exception):
    """The gateway cannot be reached at all."""


class PaymentGateway(Protocol):
    def refund(self, booking_id: str, amount: Decimal) -> None:
        """Refund `amount` for `booking_id`, or raise one of the gateway errors above."""


# --- Model ------------------------------------------------------------------

@dataclass(frozen=True)
class Room:
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def has_seat(self, row: int, seat: int) -> bool:
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    id: str
    starts_at: datetime
    room: Room
    price: Decimal

    def __post_init__(self):
        if self.starts_at.tzinfo is None:
            raise ValueError("starts_at must be timezone-aware")
        if not isinstance(self.price, Decimal) or self.price < 0:
            raise ValueError("price must be a non-negative Decimal")


class BookingStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class RefundStatus(enum.Enum):
    NOT_REQUESTED = "not_requested"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass
class Booking:
    id: str
    screening_id: str
    client_id: str
    row: int
    seat: int
    price: Decimal
    status: BookingStatus = BookingStatus.ACTIVE
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# --- Service ----------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BookingService:
    """In-memory seat booking. All public operations are serialized by a single lock."""

    def __init__(self, gateway: PaymentGateway, clock: Callable[[], datetime] = _utc_now):
        self._gateway = gateway
        self._clock = clock
        self._lock = threading.RLock()
        self._screenings: Dict[str, Screening] = {}
        self._bookings: Dict[str, Booking] = {}
        # (screening_id, row, seat) -> id of the active booking holding that seat
        self._taken_seats: Dict[tuple, str] = {}
        self._ids = itertools.count(1)

    def add_screening(self, screening: Screening) -> None:
        with self._lock:
            if screening.id in self._screenings:
                raise DuplicateScreeningError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening

    def book(self, screening_id: str, client_id: str, row: int, seat: int) -> Booking:
        with self._lock:
            screening = self._screenings.get(screening_id)
            if screening is None:
                raise ScreeningNotFoundError(f"unknown screening {screening_id!r}")
            if not screening.room.has_seat(row, seat):
                raise InvalidSeatError(f"row {row} seat {seat} does not exist in this room")
            key = (screening_id, row, seat)
            if key in self._taken_seats:
                raise SeatAlreadyBookedError(f"row {row} seat {seat} is already booked")

            booking = Booking(
                id=f"B{next(self._ids)}",
                screening_id=screening_id,
                client_id=client_id,
                row=row,
                seat=seat,
                price=screening.price,
            )
            self._bookings[booking.id] = booking
            self._taken_seats[key] = booking.id
            return booking

    def cancel(self, booking_id: str) -> Booking:
        """Cancel a booking and refund it.

        The booking is cancelled (and its seat released) only once the refund succeeds.
        - transient gateway failure: retried up to MAX_REFUND_RETRIES times;
        - permanent failure or retries exhausted: refund status FAILED, booking stays active,
          RefundFailedError is raised;
        - gateway unavailable: nothing changes, RefundUnavailableError is raised.
        """
        with self._lock:
            booking = self._get_booking(booking_id)
            if booking.status is BookingStatus.CANCELLED:
                raise BookingAlreadyCancelledError(f"booking {booking_id!r} is already cancelled")
            screening = self._screenings[booking.screening_id]
            if self._clock() > screening.starts_at - CANCELLATION_DEADLINE:
                raise CancellationTooLateError(
                    "bookings can only be cancelled up to two hours before the screening starts"
                )

            for attempt in range(1 + MAX_REFUND_RETRIES):
                try:
                    self._gateway.refund(booking.id, booking.price)
                    break
                except TransientGatewayError as exc:
                    if attempt == MAX_REFUND_RETRIES:
                        booking.refund_status = RefundStatus.FAILED
                        raise RefundFailedError(
                            f"refund for booking {booking_id!r} still failing after "
                            f"{MAX_REFUND_RETRIES} retries"
                        ) from exc
                except PermanentGatewayError as exc:
                    booking.refund_status = RefundStatus.FAILED
                    raise RefundFailedError(f"refund for booking {booking_id!r} was refused") from exc
                except GatewayUnavailableError as exc:
                    raise RefundUnavailableError(
                        "payment gateway unavailable, cancellation rejected"
                    ) from exc

            booking.refund_status = RefundStatus.REFUNDED
            booking.status = BookingStatus.CANCELLED
            del self._taken_seats[(booking.screening_id, booking.row, booking.seat)]
            return booking

    def refund_status(self, booking_id: str) -> RefundStatus:
        with self._lock:
            return self._get_booking(booking_id).refund_status

    def get_booking(self, booking_id: str) -> Booking:
        with self._lock:
            return self._get_booking(booking_id)

    def _get_booking(self, booking_id: str) -> Booking:
        booking: Optional[Booking] = self._bookings.get(booking_id)
        if booking is None:
            raise BookingNotFoundError(f"unknown booking {booking_id!r}")
        return booking
