"""Seat booking with cancellation and refund (single module, see AGENTS.md: locality)."""

import itertools
import logging
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

CANCELLATION_DEADLINE = timedelta(hours=2)
MAX_REFUND_RETRIES = 3  # retries after the first attempt


class BookingError(Exception):
    """Base class of every rejection raised by BookingService."""


class SeatAlreadyBookedError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class ScreeningStartedError(BookingError):
    pass


class UnknownBookingError(BookingError):
    pass


class AlreadyCancelledError(BookingError):
    pass


class CancellationTooLateError(BookingError):
    pass


class RefundFailedError(BookingError):
    """Permanent gateway failure (or transient failures exhausted): booking stays active."""


class RefundUnavailableError(BookingError):
    """Gateway unavailable: cancellation rejected, booking stays active."""


class TransientGatewayError(Exception):
    """Raised by a payment gateway for a failure worth retrying."""


class PermanentGatewayError(Exception):
    """Raised by a payment gateway for a failure that will not go away."""


class GatewayUnavailableError(Exception):
    """Raised by a payment gateway that cannot be reached."""


class RefundStatus:
    NOT_REQUESTED = "not_requested"
    REFUNDED = "refunded"
    FAILED = "failed"


class BookingStatus:
    ACTIVE = "active"
    CANCELLED = "cancelled"


class Room:
    def __init__(self, rows, seats_per_row):
        self.rows = rows
        self.seats_per_row = seats_per_row


class Screening:
    def __init__(self, screening_id, start_time, room, price):
        self.screening_id = screening_id
        self.start_time = start_time
        self.room = room
        self.price = Decimal(price)


class Booking:
    def __init__(self, booking_id, client, screening, row, seat):
        self.booking_id = booking_id
        self.client = client
        self.screening = screening
        self.row = row
        self.seat = seat
        self.status = BookingStatus.ACTIVE
        self.refund_status = RefundStatus.NOT_REQUESTED


class BookingService:
    """Gateway contract: gateway.refund(booking_id, amount) returns on success or raises
    TransientGatewayError / PermanentGatewayError / GatewayUnavailableError."""

    def __init__(self, payment_gateway, clock=datetime.now):
        self.payment_gateway = payment_gateway
        self.clock = clock
        self._bookings = {}
        self._ids = itertools.count(1)

    def book(self, client, screening, row, seat):
        room = screening.room
        if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
            raise InvalidSeatError(f"seat {row}/{seat} does not exist in this room")
        if self.clock() >= screening.start_time:
            raise ScreeningStartedError("screening already started")
        for existing in self._bookings.values():
            if (existing.status == BookingStatus.ACTIVE
                    and existing.screening is screening
                    and existing.row == row and existing.seat == seat):
                raise SeatAlreadyBookedError(f"seat {row}/{seat} is already booked")
        booking = Booking(next(self._ids), client, screening, row, seat)
        self._bookings[booking.booking_id] = booking
        return booking

    def cancel(self, booking_id):
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise UnknownBookingError(f"unknown booking {booking_id}")
        if booking.status == BookingStatus.CANCELLED:
            raise AlreadyCancelledError(f"booking {booking_id} is already cancelled")
        if self.clock() > booking.screening.start_time - CANCELLATION_DEADLINE:
            raise CancellationTooLateError("cancellation is only allowed up to 2 hours before the start")

        for attempt in range(1 + MAX_REFUND_RETRIES):
            try:
                self.payment_gateway.refund(booking_id, booking.screening.price)
            except TransientGatewayError:
                logger.warning("transient refund failure for booking %s (attempt %s)", booking_id, attempt + 1)
                continue
            except PermanentGatewayError as error:
                logger.error("permanent refund failure for booking %s", booking_id)
                booking.refund_status = RefundStatus.FAILED
                raise RefundFailedError("refund failed, booking stays active") from error
            except GatewayUnavailableError as error:
                logger.error("payment gateway unavailable for booking %s", booking_id)
                raise RefundUnavailableError("payment gateway unavailable, cancellation rejected") from error
            booking.status = BookingStatus.CANCELLED
            booking.refund_status = RefundStatus.REFUNDED
            return booking

        booking.refund_status = RefundStatus.FAILED
        raise RefundFailedError("refund still failing after retries, booking stays active")

    def get_refund_status(self, booking_id):
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise UnknownBookingError(f"unknown booking {booking_id}")
        return booking.refund_status
