"""Seat booking with cancellation and refund."""
import itertools
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CANCELLATION_DEADLINE = timedelta(hours=2)
MAX_REFUND_RETRIES = 3  # retries after the first attempt


class BookingError(Exception):
    """Base class of every rejection raised by the service."""


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


class CancellationTooLateError(BookingError):
    pass


class RefundUnavailableError(BookingError):
    """Gateway unavailable: cancellation rejected, booking untouched."""


class RefundFailedError(BookingError):
    """Refund failed for good: cancellation rejected, booking stays active."""


class GatewayTransientError(Exception):
    """Raised by a payment gateway for a retryable failure."""


class GatewayPermanentError(Exception):
    """Raised by a payment gateway for a non-retryable failure."""


class GatewayUnavailableError(Exception):
    """Raised by a payment gateway that cannot be reached."""


class BookingStatus:
    ACTIVE = "active"
    CANCELLED = "cancelled"


class RefundStatus:
    NONE = "none"  # nothing refunded (never cancelled, or cancellation rejected)
    REFUNDED = "refunded"
    FAILED = "failed"  # last refund attempt failed


@dataclass(frozen=True)
class Room:
    rows: int
    seats_per_row: int


@dataclass(frozen=True)
class Screening:
    id: str
    start_time: datetime
    room: Room
    price_cents: int  # integer cents: no floating point for money


@dataclass
class Booking:
    id: int
    screening_id: str
    client: str
    row: int
    seat: int
    amount_cents: int
    status: str = BookingStatus.ACTIVE
    refund_status: str = RefundStatus.NONE


class BookingService:
    """Books and cancels seats.

    `payment_gateway.refund(booking_id, amount_cents)` may raise
    GatewayTransientError, GatewayPermanentError or GatewayUnavailableError.
    """

    def __init__(self, payment_gateway, clock=datetime.now):
        self._gateway = payment_gateway
        self._clock = clock
        self._screenings = {}
        self._bookings = {}
        self._ids = itertools.count(1)

    def add_screening(self, screening):
        self._screenings[screening.id] = screening

    def book(self, screening_id, client, row, seat):
        screening = self._screenings.get(screening_id)
        if screening is None:
            raise UnknownScreeningError(screening_id)
        room = screening.room
        if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
            raise InvalidSeatError((row, seat))
        for existing in self._bookings.values():
            if (existing.status == BookingStatus.ACTIVE
                    and existing.screening_id == screening_id
                    and (existing.row, existing.seat) == (row, seat)):
                raise SeatAlreadyBookedError((row, seat))
        booking = Booking(next(self._ids), screening_id, client, row, seat,
                          screening.price_cents)
        self._bookings[booking.id] = booking
        return booking

    def cancel(self, booking_id):
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise UnknownBookingError(booking_id)
        if booking.status == BookingStatus.CANCELLED:
            raise BookingAlreadyCancelledError(booking_id)
        start = self._screenings[booking.screening_id].start_time
        if self._clock() > start - CANCELLATION_DEADLINE:
            raise CancellationTooLateError(booking_id)

        for attempt in range(1 + MAX_REFUND_RETRIES):
            try:
                self._gateway.refund(booking.id, booking.amount_cents)
            except GatewayTransientError:
                logger.warning("refund attempt %d failed for booking %s",
                               attempt + 1, booking.id)
                continue
            except GatewayPermanentError as error:
                logger.error("refund failed permanently for booking %s", booking.id)
                booking.refund_status = RefundStatus.FAILED
                raise RefundFailedError(booking.id) from error
            except GatewayUnavailableError as error:
                logger.error("payment gateway unavailable for booking %s", booking.id)
                raise RefundUnavailableError(booking.id) from error
            booking.status = BookingStatus.CANCELLED
            booking.refund_status = RefundStatus.REFUNDED
            return booking
        # Transient errors used up every attempt: treated like a failed refund.
        logger.error("refund retries exhausted for booking %s", booking.id)
        booking.refund_status = RefundStatus.FAILED
        raise RefundFailedError(booking.id)

    def refund_status(self, booking_id):
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise UnknownBookingError(booking_id)
        return booking.refund_status
