"""Seat booking for screenings, with cancellation and refund through a payment gateway."""

import enum
import itertools
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Module logger, so every rejection and gateway failure is observable.
logger = logging.getLogger(__name__)

# Latest moment before the start of a screening at which a booking can still be cancelled.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Number of retries after a first transient gateway failure (so up to 4 attempts in total).
MAX_REFUND_RETRIES = 3


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class BookingError(Exception):
    """Base class for every rejection raised by the booking service."""


class UnknownScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


class UnknownBookingError(BookingError):
    pass


class BookingAlreadyCancelledError(BookingError):
    pass


class CancellationDeadlinePassedError(BookingError):
    pass


class RefundGatewayUnavailableError(BookingError):
    """The gateway could not be reached: the cancellation is rejected, nothing changed."""


class RefundFailedError(BookingError):
    """The refund failed (permanently, or after exhausting retries): the booking stays active."""


# Errors the payment gateway is expected to raise from `refund`.
class TransientGatewayError(Exception):
    pass


class PermanentGatewayError(Exception):
    pass


class GatewayUnavailableError(Exception):
    pass


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Room:
    name: str
    rows: int
    seats_per_row: int


@dataclass(frozen=True)
class Screening:
    screening_id: str
    start_time: datetime
    room: Room
    price: Decimal


class BookingStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class RefundStatus(enum.Enum):
    NOT_REQUESTED = "not_requested"
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


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BookingService:
    """In-memory booking service.

    `payment_gateway` must expose `refund(booking_id, amount)` and raise
    TransientGatewayError, PermanentGatewayError or GatewayUnavailableError on failure.
    `clock` returns the current time; it defaults to UTC now and is injectable for tests.
    """

    def __init__(self, payment_gateway, clock=None):
        self._gateway = payment_gateway
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._screenings = {}
        self._bookings = {}
        # (screening_id, row, seat) -> booking_id, for active bookings only.
        self._booked_seats = {}
        self._ids = itertools.count(1)
        # Serializes book/cancel so a seat cannot be booked twice concurrently,
        # nor a booking cancelled (and refunded) twice.
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            self._screenings[screening.screening_id] = screening

    def book(self, screening_id, client_id, row, seat):
        with self._lock:
            screening = self._screenings.get(screening_id)
            if screening is None:
                logger.warning("Booking rejected: unknown screening %s", screening_id)
                raise UnknownScreeningError(screening_id)
            room = screening.room
            if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
                logger.warning("Booking rejected: seat %s/%s outside room %s", row, seat, room.name)
                raise InvalidSeatError(f"row {row}, seat {seat} not in room {room.name}")
            key = (screening_id, row, seat)
            if key in self._booked_seats:
                logger.warning("Booking rejected: seat %s already booked", key)
                raise SeatAlreadyBookedError(f"row {row}, seat {seat} already booked for {screening_id}")
            booking = Booking(
                booking_id=f"B{next(self._ids)}",
                screening_id=screening_id,
                client_id=client_id,
                row=row,
                seat=seat,
                amount=screening.price,
            )
            self._bookings[booking.booking_id] = booking
            self._booked_seats[key] = booking.booking_id
            return booking

    def cancel(self, booking_id):
        """Cancel a booking and refund it. Returns the cancelled booking.

        Rejections leave the booking active. A failed refund also leaves it active
        and marks its refund status FAILED; the client may try cancelling again.
        """
        with self._lock:
            booking = self._bookings.get(booking_id)
            if booking is None:
                logger.warning("Cancellation rejected: unknown booking %s", booking_id)
                raise UnknownBookingError(booking_id)
            if booking.status is BookingStatus.CANCELLED:
                logger.warning("Cancellation rejected: booking %s already cancelled", booking_id)
                raise BookingAlreadyCancelledError(booking_id)
            screening = self._screenings[booking.screening_id]
            if self._clock() > screening.start_time - CANCELLATION_DEADLINE:
                logger.warning("Cancellation rejected: deadline passed for booking %s", booking_id)
                raise CancellationDeadlinePassedError(booking_id)

            attempt = 0
            while True:
                attempt += 1
                try:
                    self._gateway.refund(booking.booking_id, booking.amount)
                    break
                except GatewayUnavailableError as error:
                    logger.warning("Refund gateway unavailable for booking %s", booking_id)
                    raise RefundGatewayUnavailableError(booking_id) from error
                except PermanentGatewayError as error:
                    logger.error("Refund permanently failed for booking %s", booking_id)
                    booking.refund_status = RefundStatus.FAILED
                    raise RefundFailedError(booking_id) from error
                except TransientGatewayError as error:
                    if attempt > MAX_REFUND_RETRIES:
                        logger.error("Refund for booking %s still failing after %d attempts", booking_id, attempt)
                        booking.refund_status = RefundStatus.FAILED
                        raise RefundFailedError(booking_id) from error
                    logger.info("Transient refund failure for booking %s (attempt %d), retrying", booking_id, attempt)

            booking.status = BookingStatus.CANCELLED
            booking.refund_status = RefundStatus.REFUNDED
            del self._booked_seats[(booking.screening_id, booking.row, booking.seat)]
            return booking

    def refund_status(self, booking_id):
        with self._lock:
            booking = self._bookings.get(booking_id)
            if booking is None:
                raise UnknownBookingError(booking_id)
            return booking.refund_status
