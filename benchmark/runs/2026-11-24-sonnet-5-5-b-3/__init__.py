# Logging module used to record every exception at every layer.
import logging
# Dataclasses give plain data entities (fields only).
from dataclasses import dataclass
# Time arithmetic for the cancellation deadline.
from datetime import datetime, timedelta

# Module logger.
logger = logging.getLogger(__name__)

# Booking is live and holds its seat.
STATUS_ACTIVE = "ACTIVE"
# Booking was cancelled and the seat is free again.
STATUS_CANCELLED = "CANCELLED"
# No refund was ever requested for the booking.
REFUND_NONE = "NONE"
# The gateway confirmed the refund.
REFUND_REFUNDED = "REFUNDED"
# The gateway failed permanently (or transient retries ran out).
REFUND_FAILED = "FAILED"
# The gateway was unavailable.
REFUND_UNAVAILABLE = "UNAVAILABLE"

# Cancellation allowed up to this long before the screening starts.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Number of retries after the first attempt on a transient failure.
MAX_REFUND_RETRIES = 3


# Generic exception exposed at the service boundary.
class ProcessingException(Exception):
    pass


# Seat is already held by an active booking.
class SeatAlreadyBookedException(ProcessingException):
    pass


# Seat does not exist in the room, or screening unknown/started.
class InvalidBookingRequestException(ProcessingException):
    pass


# Booking id is unknown.
class BookingNotFoundException(ProcessingException):
    pass


# Booking was already cancelled.
class BookingAlreadyCancelledException(ProcessingException):
    pass


# Less than two hours remain before the screening.
class CancellationTooLateException(ProcessingException):
    pass


# Refund permanently failed; booking stays active.
class RefundFailedException(ProcessingException):
    pass


# Gateway unavailable; cancellation rejected.
class RefundUnavailableException(ProcessingException):
    pass


# Gateway failure that may succeed if retried.
class TransientGatewayError(Exception):
    pass


# Gateway failure that will never succeed.
class PermanentGatewayError(Exception):
    pass


# Gateway cannot be reached at all.
class GatewayUnavailableError(Exception):
    pass


# Room: plain data, rows x seats per row.
@dataclass
class Room:
    rows: int
    seats_per_row: int


# Screening: plain data. Price is an integer number of cents (exact money).
@dataclass
class Screening:
    screening_id: str
    start_time: datetime
    room: Room
    price_cents: int


# Booking: plain data.
@dataclass
class Booking:
    booking_id: str
    screening_id: str
    client_id: str
    row: int
    seat: int
    price_cents: int
    status: str = STATUS_ACTIVE
    refund_status: str = REFUND_NONE


# Service holding the booking rules; gateway and clock are passed in.
class BookingManager:
    # Gateway must expose refund(booking_id, amount_cents).
    def __init__(self, gateway, clock=datetime.now):
        # Payment gateway used for refunds.
        self.gateway = gateway
        # Clock, injectable for deterministic tests.
        self.clock = clock
        # Screenings by id.
        self.screenings = {}
        # Bookings by id.
        self.bookings = {}
        # Counter used to build booking ids.
        self.sequence = 0

    # Register a screening so seats can be booked on it.
    def add_screening(self, screening):
        # Store it under its id.
        self.screenings[screening.screening_id] = screening

    # Book one seat; returns the new Booking.
    def book_seat(self, client_id, screening_id, row, seat):
        # Log every exception, wrap it in the generic exception, rethrow.
        try:
            # Do the real work.
            return self._book_seat(client_id, screening_id, row, seat)
        # Our own rejections already are ProcessingException subclasses.
        except ProcessingException as exc:
            # Record the failure.
            logger.error("book_seat failed: %s", exc)
            # Rethrow unchanged so callers can tell rejections apart.
            raise
        # Anything unexpected from a lower layer.
        except Exception as exc:
            # Record the failure.
            logger.error("book_seat failed: %s", exc)
            # Wrap in the generic exception (cause omitted, per AGENTS.md).
            raise ProcessingException("booking failed") from None

    # Booking rules.
    def _book_seat(self, client_id, screening_id, row, seat):
        # Look the screening up.
        screening = self.screenings.get(screening_id)
        # Unknown screening.
        if screening is None:
            # Reject.
            raise InvalidBookingRequestException("unknown screening")
        # Seat must exist in the room (rows and seats are 1-based).
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            # Reject.
            raise InvalidBookingRequestException("no such seat")
        # No booking once the screening has started.
        if self.clock() >= screening.start_time:
            # Reject.
            raise InvalidBookingRequestException("screening already started")
        # Check every active booking for the same seat.
        for existing in self.bookings.values():
            # Same screening, same seat, still active.
            if (existing.screening_id == screening_id and existing.row == row
                    and existing.seat == seat and existing.status == STATUS_ACTIVE):
                # Reject the double booking.
                raise SeatAlreadyBookedException("seat already booked")
        # Next sequence number.
        self.sequence += 1
        # Build the booking, freezing the price paid.
        booking = Booking("B%d" % self.sequence, screening_id, client_id, row, seat,
                          screening.price_cents)
        # Store it.
        self.bookings[booking.booking_id] = booking
        # Hand it back.
        return booking

    # Cancel a booking and refund it; returns the cancelled Booking.
    def cancel_booking(self, booking_id):
        # Log every exception, wrap it in the generic exception, rethrow.
        try:
            # Do the real work.
            return self._cancel_booking(booking_id)
        # Our own rejections already are ProcessingException subclasses.
        except ProcessingException as exc:
            # Record the failure.
            logger.error("cancel_booking failed: %s", exc)
            # Rethrow unchanged so callers can tell rejections apart.
            raise
        # Anything unexpected from a lower layer.
        except Exception as exc:
            # Record the failure.
            logger.error("cancel_booking failed: %s", exc)
            # Wrap in the generic exception (cause omitted, per AGENTS.md).
            raise ProcessingException("cancellation failed") from None

    # Cancellation rules.
    def _cancel_booking(self, booking_id):
        # Look the booking up.
        booking = self.bookings.get(booking_id)
        # Unknown booking.
        if booking is None:
            # Reject.
            raise BookingNotFoundException("unknown booking")
        # Already cancelled.
        if booking.status == STATUS_CANCELLED:
            # Reject.
            raise BookingAlreadyCancelledException("booking already cancelled")
        # Deadline: two hours before start (exactly two hours is still allowed).
        deadline = self.screenings[booking.screening_id].start_time - CANCELLATION_DEADLINE
        # Too late.
        if self.clock() > deadline:
            # Reject.
            raise CancellationTooLateException("less than two hours before screening")
        # First attempt plus the allowed retries.
        for attempt in range(MAX_REFUND_RETRIES + 1):
            # Try the refund.
            try:
                # Call the gateway.
                self.gateway.refund(booking.booking_id, booking.price_cents)
            # Transient failure: retry unless attempts are exhausted.
            except TransientGatewayError as exc:
                # Record it.
                logger.error("transient refund failure (attempt %d): %s", attempt + 1, exc)
                # Retries left: go around again.
                if attempt < MAX_REFUND_RETRIES:
                    # Next attempt.
                    continue
                # Out of retries: treat like a failed refund, booking stays active.
                booking.refund_status = REFUND_FAILED
                # Reject.
                raise RefundFailedException("refund failed after retries") from None
            # Permanent failure: booking stays active.
            except PermanentGatewayError as exc:
                # Record it.
                logger.error("permanent refund failure: %s", exc)
                # Expose the failure.
                booking.refund_status = REFUND_FAILED
                # Reject.
                raise RefundFailedException("refund failed") from None
            # Gateway down: cancellation rejected, booking stays active.
            except GatewayUnavailableError as exc:
                # Record it.
                logger.error("gateway unavailable: %s", exc)
                # Expose the state.
                booking.refund_status = REFUND_UNAVAILABLE
                # Reject.
                raise RefundUnavailableException("payment gateway unavailable") from None
            # Refund went through.
            booking.status = STATUS_CANCELLED
            # Expose the state.
            booking.refund_status = REFUND_REFUNDED
            # Done.
            return booking

    # Refund status of a booking.
    def get_refund_status(self, booking_id):
        # Log every exception, wrap it in the generic exception, rethrow.
        try:
            # Look the booking up.
            booking = self.bookings.get(booking_id)
            # Unknown booking.
            if booking is None:
                # Reject.
                raise BookingNotFoundException("unknown booking")
            # Report its refund status.
            return booking.refund_status
        # Our own rejections already are ProcessingException subclasses.
        except ProcessingException as exc:
            # Record the failure.
            logger.error("get_refund_status failed: %s", exc)
            # Rethrow unchanged.
            raise
