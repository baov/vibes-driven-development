# Standard logging, used to record every failure before it is rethrown.
import logging
# Dataclasses give us plain data entities.
from dataclasses import dataclass
# Datetime types for screening start, clock and cancellation deadline.
from datetime import datetime, timedelta
# Decimal keeps money exact (a deliberate exception to "primitives over value objects").
from decimal import Decimal
# Enums name the booking and refund states.
from enum import Enum

# Module logger.
logger = logging.getLogger(__name__)

# A booking can be cancelled up to this long before the screening starts.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Number of retries after the first refund attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3

# Machine-readable rejection reasons carried by ProcessingException.
REASON_INVALID_SEAT = "INVALID_SEAT"
REASON_SCREENING_STARTED = "SCREENING_STARTED"
REASON_SEAT_ALREADY_BOOKED = "SEAT_ALREADY_BOOKED"
REASON_UNKNOWN_BOOKING = "UNKNOWN_BOOKING"
REASON_ALREADY_CANCELLED = "ALREADY_CANCELLED"
REASON_TOO_LATE_TO_CANCEL = "TOO_LATE_TO_CANCEL"
REASON_REFUND_FAILED = "REFUND_FAILED"
REASON_GATEWAY_UNAVAILABLE = "GATEWAY_UNAVAILABLE"
REASON_INTERNAL = "INTERNAL"


# Generic exception exposed at the service boundary (AGENTS.md section 4).
class ProcessingException(Exception):
    # Store the reason code next to the human-readable message.
    def __init__(self, reason, message=""):
        # Initialise the base exception with a readable message.
        super().__init__(message or reason)
        # Keep the reason so callers can branch on it.
        self.reason = reason


# Gateway contract: failures a payment gateway may raise.
class TransientGatewayError(Exception):
    pass


class PermanentGatewayError(Exception):
    pass


class GatewayUnavailableError(Exception):
    pass


# Lifecycle of a booking.
class BookingStatus(Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


# Refund state exposed to clients.
class RefundStatus(Enum):
    # No refund was requested or none succeeded yet.
    NONE = "NONE"
    # The gateway confirmed the refund.
    REFUNDED = "REFUNDED"
    # The gateway failed for good; the booking stays active.
    FAILED = "FAILED"


# A room is a grid of rows and seats.
@dataclass
class Room:
    rows: int
    seats_per_row: int


# A screening has a start time, a room and a price.
@dataclass
class Screening:
    id: str
    start_time: datetime
    room: Room
    price: Decimal


# A client's booking of one seat for one screening.
@dataclass
class Booking:
    id: int
    client_id: str
    screening: Screening
    row: int
    seat: int
    status: BookingStatus = BookingStatus.ACTIVE
    refund_status: RefundStatus = RefundStatus.NONE


# Business rules live in the service; the gateway and clock are passed in.
class BookingService:
    # Receive the payment gateway (needs a refund(booking_id, amount) method) and a clock.
    def __init__(self, payment_gateway, clock=datetime.now):
        # Keep the gateway used for refunds.
        self.payment_gateway = payment_gateway
        # Keep the clock so tests control "now".
        self.clock = clock
        # Bookings indexed by id.
        self.bookings = {}
        # Next booking id to hand out.
        self.next_id = 1

    # Book one seat (1-based row and seat numbers) of a screening for a client.
    def book_seat(self, client_id, screening, row, seat):
        # Log and rethrow every failure.
        try:
            # Reject seats outside the room.
            if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                # Seat does not exist.
                raise ProcessingException(REASON_INVALID_SEAT, "seat does not exist in this room")
            # Reject bookings for screenings that already started.
            if self.clock() >= screening.start_time:
                # Too late to book.
                raise ProcessingException(REASON_SCREENING_STARTED, "screening already started")
            # Look at every existing booking.
            for existing in self.bookings.values():
                # Only an active booking of the same seat for the same screening blocks the seat.
                if (existing.status == BookingStatus.ACTIVE and existing.screening.id == screening.id
                        and existing.row == row and existing.seat == seat):
                    # Seat is taken.
                    raise ProcessingException(REASON_SEAT_ALREADY_BOOKED, "seat already booked")
            # Create the booking.
            booking = Booking(self.next_id, client_id, screening, row, seat)
            # Consume the id.
            self.next_id += 1
            # Store the booking.
            self.bookings[booking.id] = booking
            # Hand it back.
            return booking
        # Business rejections: log, then rethrow unchanged.
        except ProcessingException:
            logger.exception("book_seat rejected")
            raise
        # Anything unexpected: log, then wrap in the generic exception.
        except Exception as error:
            logger.exception("book_seat failed")
            raise ProcessingException(REASON_INTERNAL, "booking failed") from error

    # Cancel a booking and refund it through the gateway.
    def cancel_booking(self, booking_id):
        # Log and rethrow every failure.
        try:
            # Find the booking.
            booking = self.bookings.get(booking_id)
            # Unknown booking is rejected.
            if booking is None:
                raise ProcessingException(REASON_UNKNOWN_BOOKING, "unknown booking")
            # Already cancelled booking is rejected.
            if booking.status == BookingStatus.CANCELLED:
                raise ProcessingException(REASON_ALREADY_CANCELLED, "booking already cancelled")
            # Cancellation closes two hours before the start (exactly two hours is still allowed).
            if self.clock() > booking.screening.start_time - CANCELLATION_DEADLINE:
                raise ProcessingException(REASON_TOO_LATE_TO_CANCEL, "less than two hours before the screening")
            # Count retries already used.
            retries = 0
            # Try the refund until it succeeds or we give up.
            while True:
                # Ask the gateway to refund the screening price.
                try:
                    self.payment_gateway.refund(booking.id, booking.screening.price)
                    # Success: stop retrying.
                    break
                # Transient failure: retry while retries remain.
                except TransientGatewayError as error:
                    # Out of retries: treat like a failed refund, booking stays active.
                    if retries >= MAX_REFUND_RETRIES:
                        booking.refund_status = RefundStatus.FAILED
                        raise ProcessingException(REASON_REFUND_FAILED, "refund kept failing") from error
                    # Count this retry.
                    retries += 1
                # Permanent failure: record it, booking stays active.
                except PermanentGatewayError as error:
                    booking.refund_status = RefundStatus.FAILED
                    raise ProcessingException(REASON_REFUND_FAILED, "refund refused") from error
                # Gateway down: reject the cancellation, nothing recorded so it can be retried later.
                except GatewayUnavailableError as error:
                    raise ProcessingException(REASON_GATEWAY_UNAVAILABLE, "payment gateway unavailable") from error
            # Refund went through: cancel the booking.
            booking.status = BookingStatus.CANCELLED
            # Record the refund.
            booking.refund_status = RefundStatus.REFUNDED
            # Hand back the updated booking.
            return booking
        # Business rejections: log, then rethrow unchanged.
        except ProcessingException:
            logger.exception("cancel_booking rejected")
            raise
        # Anything unexpected: log, then wrap in the generic exception.
        except Exception as error:
            logger.exception("cancel_booking failed")
            raise ProcessingException(REASON_INTERNAL, "cancellation failed") from error

    # Expose the refund status of a booking.
    def get_refund_status(self, booking_id):
        # Find the booking.
        booking = self.bookings.get(booking_id)
        # Unknown booking is rejected (logged first).
        if booking is None:
            logger.error("get_refund_status: unknown booking %s", booking_id)
            raise ProcessingException(REASON_UNKNOWN_BOOKING, "unknown booking")
        # Report the status.
        return booking.refund_status
