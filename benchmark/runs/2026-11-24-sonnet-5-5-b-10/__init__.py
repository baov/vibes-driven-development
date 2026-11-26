# Standard library dataclass support for plain data entities
from dataclasses import dataclass
# Standard library date helpers used for the cancellation deadline
from datetime import datetime, timedelta
# Standard library logging used to log every exception at every layer
import logging

# Module logger used by the manager service
logger = logging.getLogger(__name__)

# Number of retries allowed after the first refund attempt on a transient failure
MAX_REFUND_RETRIES = 3
# Number of hours before the start of a screening after which cancelling is refused
CANCELLATION_DEADLINE_HOURS = 2


# Generic exception exposed at the layer boundary, original cause deliberately omitted
class ProcessingException(Exception):
    # Marker body, the class carries no extra behavior
    pass


# Raised when a booking request is refused
class BookingRejectedException(ProcessingException):
    # Marker body, the class carries no extra behavior
    pass


# Raised when a cancellation or a lookup on a booking is refused
class CancellationRejectedException(ProcessingException):
    # Marker body, the class carries no extra behavior
    pass


# Gateway failure that may succeed if the refund is attempted again
class GatewayTransientError(Exception):
    # Marker body, the class carries no extra behavior
    pass


# Gateway failure that will never succeed for this refund
class GatewayPermanentError(Exception):
    # Marker body, the class carries no extra behavior
    pass


# Gateway is down, no refund can be attempted
class GatewayUnavailableError(Exception):
    # Marker body, the class carries no extra behavior
    pass


# Plain data: a room is a grid of rows and seats (numbered from 1)
@dataclass
class Room:
    # Number of rows in the room
    rows: int
    # Number of seats in each row
    seats_per_row: int


# Plain data: a screening of a room at a given time and price
@dataclass
class Screening:
    # Identifier of the screening
    screening_id: str
    # Start time of the screening
    start_time: datetime
    # Room where the screening takes place
    room: Room
    # Price of one seat
    price: float


# Plain data: the booking of one seat by one client
@dataclass
class Booking:
    # Identifier of the booking
    booking_id: str
    # Screening the seat is booked for
    screening: Screening
    # Client who booked the seat
    client_id: str
    # Row of the seat
    row: int
    # Seat number in the row
    seat: int
    # ACTIVE or CANCELLED
    status: str = "ACTIVE"
    # NONE (no refund requested), REFUNDED or FAILED
    refund_status: str = "NONE"


# Business logic for booking, cancelling and refunding seats
class BookingManagerService:
    # The gateway must expose refund(booking_id, amount) and may raise the Gateway*Error exceptions
    def __init__(self, gateway, now_provider=None):
        # Payment gateway used for refunds
        self.gateway = gateway
        # Clock, defaults to the system clock
        self.now_provider = now_provider or datetime.now
        # Known screenings by identifier
        self.screenings = {}
        # Known bookings by identifier
        self.bookings = {}
        # Counter used to generate booking identifiers
        self.booking_counter = 0

    # Makes a screening known to the service
    def register_screening(self, screening):
        # Store the screening under its identifier
        self.screenings[screening.screening_id] = screening

    # Books a seat for a client, rejects unknown screenings, started screenings, invalid and taken seats
    def book_seat(self, screening_id, client_id, row, seat):
        # Layer boundary: every exception is logged then rethrown
        try:
            # Look up the screening
            screening = self.screenings.get(screening_id)
            # Reject an unknown screening
            if screening is None:
                # Refuse the booking
                raise BookingRejectedException("unknown screening")
            # Reject a screening that has already started
            if self.now_provider() >= screening.start_time:
                # Refuse the booking
                raise BookingRejectedException("screening already started")
            # Reject a seat that does not exist in the room
            if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                # Refuse the booking
                raise BookingRejectedException("unknown seat")
            # Check every booking for a still active one on the same seat
            for info in self.bookings.values():
                # An active booking on the same screening and seat means the seat is taken
                if (info.status == "ACTIVE" and info.screening.screening_id == screening_id
                        and info.row == row and info.seat == seat):
                    # Refuse the booking
                    raise BookingRejectedException("seat already booked")
            # Generate the next booking identifier
            self.booking_counter += 1
            # Create the booking
            result = Booking(str(self.booking_counter), screening, client_id, row, seat)
            # Store the booking
            self.bookings[result.booking_id] = result
            # Hand the booking back to the caller
            return result
        # Domain rejections pass through the layer
        except ProcessingException:
            # Log the exception
            logger.exception("book_seat rejected")
            # Rethrow it
            raise
        # Anything else is wrapped to avoid leaking implementation details
        except Exception:
            # Log the exception
            logger.exception("book_seat failed")
            # Rethrow as a generic exception, the original cause is omitted
            raise ProcessingException("booking failed") from None

    # Cancels a booking up to two hours before the screening and refunds it through the gateway
    def cancel_booking(self, booking_id):
        # Layer boundary: every exception is logged then rethrown
        try:
            # Look up the booking
            booking = self.bookings.get(booking_id)
            # Reject an unknown booking
            if booking is None:
                # Refuse the cancellation
                raise CancellationRejectedException("unknown booking")
            # Reject a booking that is already cancelled
            if booking.status == "CANCELLED":
                # Refuse the cancellation
                raise CancellationRejectedException("booking already cancelled")
            # Compute the last moment at which cancelling is allowed
            deadline = booking.screening.start_time - timedelta(hours=CANCELLATION_DEADLINE_HOURS)
            # Reject a cancellation made after the deadline
            if self.now_provider() > deadline:
                # Refuse the cancellation
                raise CancellationRejectedException("too late to cancel")
            # Outcome of the refund: REFUNDED, FAILED or UNAVAILABLE
            data = "FAILED"
            # One first attempt then up to MAX_REFUND_RETRIES retries
            for attempt in range(MAX_REFUND_RETRIES + 1):
                # Try to refund the price of the seat
                try:
                    # Call the payment gateway
                    self.gateway.refund(booking.booking_id, booking.screening.price)
                    # Refund went through
                    data = "REFUNDED"
                    # Stop retrying
                    break
                # Transient failure: try again, while attempts remain
                except GatewayTransientError:
                    # Log the transient failure
                    logger.warning("transient refund failure, attempt %s", attempt + 1)
                    # Retries exhausted leave the outcome as FAILED
                    data = "FAILED"
                # Permanent failure: no point in retrying
                except GatewayPermanentError:
                    # Log the permanent failure
                    logger.exception("permanent refund failure")
                    # Record the failure
                    data = "FAILED"
                    # Stop retrying
                    break
                # Gateway down: no point in retrying
                except GatewayUnavailableError:
                    # Log the unavailability
                    logger.exception("payment gateway unavailable")
                    # Record the unavailability
                    data = "UNAVAILABLE"
                    # Stop retrying
                    break
            # Refund succeeded: the cancellation is effective
            if data == "REFUNDED":
                # Cancel the booking, which frees the seat
                booking.status = "CANCELLED"
                # Record the refund
                booking.refund_status = "REFUNDED"
                # Hand the booking back to the caller
                return booking
            # Refund failed for good: booking stays active, failure is exposed as refund status
            if data == "FAILED":
                # Record the failed refund
                booking.refund_status = "FAILED"
                # Refuse the cancellation
                raise CancellationRejectedException("refund failed, booking stays active")
            # Gateway unavailable: nothing is recorded, the cancellation is rejected
            raise CancellationRejectedException("payment gateway unavailable")
        # Domain rejections pass through the layer
        except ProcessingException:
            # Log the exception
            logger.exception("cancel_booking rejected")
            # Rethrow it
            raise
        # Anything else is wrapped to avoid leaking implementation details
        except Exception:
            # Log the exception
            logger.exception("cancel_booking failed")
            # Rethrow as a generic exception, the original cause is omitted
            raise ProcessingException("cancellation failed") from None

    # Exposes the refund status of a booking: NONE, REFUNDED or FAILED
    def get_refund_status(self, booking_id):
        # Layer boundary: every exception is logged then rethrown
        try:
            # Look up the booking
            booking = self.bookings.get(booking_id)
            # Reject an unknown booking
            if booking is None:
                # Refuse the lookup
                raise CancellationRejectedException("unknown booking")
            # Hand the refund status back to the caller
            return booking.refund_status
        # Domain rejections pass through the layer
        except ProcessingException:
            # Log the exception
            logger.exception("get_refund_status rejected")
            # Rethrow it
            raise
