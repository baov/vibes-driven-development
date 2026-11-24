# Import the standard logging module so every layer can record its failures
import logging
# Import Enum to model booking and refund states as fixed sets of values
from enum import Enum
# Import datetime and timedelta for screening times and the cancellation cutoff
from datetime import datetime, timedelta, timezone
# Import dataclass to declare the plain data entities
from dataclasses import dataclass

# Create the module logger used by every layer in this module
logger = logging.getLogger(__name__)

# Define how long before the start a booking can still be cancelled
CANCELLATION_CUTOFF = timedelta(hours=2)
# Define how many times a transiently failing refund is retried after the first attempt
MAX_REFUND_RETRIES = 3


# Generic exception raised at the service boundary so callers never see gateway details
class ProcessingException(Exception):
    """Generic failure raised by BookingManager for rejections and gateway problems."""


# Signal from the gateway that a refund failed temporarily and may succeed on retry
class TransientGatewayException(Exception):
    """A refund failed temporarily; retrying may succeed."""


# Signal from the gateway that a refund was refused for good
class PermanentGatewayException(Exception):
    """A refund was refused permanently."""


# Signal from the gateway that it cannot be reached right now
class GatewayUnavailableException(Exception):
    """The payment gateway is unavailable."""


# Lifecycle states of a booking
class BookingStatus(Enum):
    # A booking that holds its seat
    ACTIVE = "ACTIVE"
    # A booking whose seat has been released by a cancellation
    CANCELLED = "CANCELLED"


# Refund states exposed to clients
class RefundStatus(Enum):
    # No refund has been attempted for the booking
    NOT_REQUESTED = "NOT_REQUESTED"
    # The gateway confirmed the refund
    REFUNDED = "REFUNDED"
    # The gateway refused the refund permanently
    FAILED = "FAILED"


# Physical room whose seats are numbered from 1 in every row
@dataclass
class Room:
    # Number of rows in the room
    rows: int
    # Number of seats in every row
    seats_per_row: int


# A showing of a film at a fixed time, in a fixed room, at a fixed price
@dataclass
class Screening:
    # Unique identifier of the screening
    screening_id: str
    # Timezone-aware start time of the screening
    start_time: datetime
    # Room where the screening takes place
    room: Room
    # Price of one seat in cents
    price_cents: int


# A client's reservation of one seat for one screening
@dataclass
class Booking:
    # Unique identifier of the booking
    booking_id: int
    # Identifier of the screening the seat belongs to
    screening_id: str
    # Row of the booked seat, starting at 1
    row: int
    # Seat number within the row, starting at 1
    seat_number: int
    # Amount paid for the seat in cents, refunded on cancellation
    amount_cents: int
    # Whether the booking still holds its seat
    status: BookingStatus = BookingStatus.ACTIVE
    # Outcome of the refund attempted on cancellation
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# Service that books seats, cancels bookings and tracks refunds through a payment gateway
class BookingManager:
    """The gateway is passed in and must provide refund(booking_id, amount_cents)."""

    # Store the collaborators and the in-memory registries
    def __init__(self, gateway, clock=None):
        # Keep the payment gateway used for refunds
        self._gateway = gateway
        # Use the supplied clock, or the real UTC clock when none is given
        self._clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        # Index screenings by their identifier
        self._screenings = {}
        # Index bookings by their identifier
        self._bookings = {}
        # Counter that hands out the next booking identifier
        self._next_booking_id = 1

    # Register a screening so that seats can be booked for it
    def add_screening(self, screening):
        # Store the screening under its identifier
        self._screenings[screening.screening_id] = screening

    # Reserve one seat for a screening, rejecting unknown screenings, invalid seats and double bookings
    def book_seat(self, screening_id, row, seat_number):
        # Look up the screening the client wants to book
        screening = self._screenings.get(screening_id)
        # Check whether the screening exists
        if screening is None:
            # Log the rejection before raising it
            logger.error("Booking rejected: unknown screening %s", screening_id)
            # Raise the generic exception so no storage details leak
            raise ProcessingException("Unknown screening")
        # Check whether the seat lies inside the room
        if not (1 <= row <= screening.room.rows and 1 <= seat_number <= screening.room.seats_per_row):
            # Log the rejection before raising it
            logger.error("Booking rejected: seat %s/%s does not exist for screening %s", row, seat_number, screening_id)
            # Raise the generic exception for an invalid seat
            raise ProcessingException("Seat does not exist in the room")
        # Check whether an active booking already holds this seat for this screening
        if any(b.screening_id == screening_id and b.row == row and b.seat_number == seat_number and b.status is BookingStatus.ACTIVE for b in self._bookings.values()):
            # Log the rejection before raising it
            logger.error("Booking rejected: seat %s/%s already booked for screening %s", row, seat_number, screening_id)
            # Raise the generic exception for a double booking
            raise ProcessingException("Seat already booked")
        # Create the booking, recording the price paid so it can be refunded later
        booking = Booking(self._next_booking_id, screening_id, row, seat_number, screening.price_cents)
        # Advance the identifier counter so the next booking gets a new identifier
        self._next_booking_id += 1
        # Store the new booking so it can be cancelled or queried later
        self._bookings[booking.booking_id] = booking
        # Return the booking to the caller
        return booking

    # Cancel an active booking up to the cutoff and refund it through the gateway
    def cancel_booking(self, booking_id):
        # Look up the booking the client wants to cancel
        booking = self._bookings.get(booking_id)
        # Check whether the booking exists
        if booking is None:
            # Log the rejection before raising it
            logger.error("Cancellation rejected: unknown booking %s", booking_id)
            # Raise the generic exception for an unknown booking
            raise ProcessingException("Unknown booking")
        # Check whether the booking was already cancelled
        if booking.status is BookingStatus.CANCELLED:
            # Log the rejection before raising it
            logger.error("Cancellation rejected: booking %s already cancelled", booking_id)
            # Raise the generic exception for a repeated cancellation
            raise ProcessingException("Booking already cancelled")
        # Find the screening to read its start time for the cancellation deadline
        screening = self._screenings[booking.screening_id]
        # Check whether the cancellation deadline has passed
        if self._clock() > screening.start_time - CANCELLATION_CUTOFF:
            # Log the rejection before raising it
            logger.error("Cancellation rejected: deadline passed for booking %s", booking_id)
            # Raise the generic exception for a late cancellation
            raise ProcessingException("Cancellation deadline has passed")
        # Count the retries already made for a transiently failing refund
        retries = 0
        # Attempt the refund, retrying transient failures up to the limit
        while True:
            try:
                # Ask the gateway to refund the amount paid for the seat
                self._gateway.refund(booking.booking_id, booking.amount_cents)
                # Stop retrying because the refund succeeded
                break
            except TransientGatewayException:
                # Log the transient failure before deciding whether to retry
                logger.warning("Transient refund failure for booking %s after %s retries", booking_id, retries)
                # Check whether the retry budget is spent
                if retries >= MAX_REFUND_RETRIES:
                    # Log the final failure before raising it
                    logger.error("Cancellation rejected: refund for booking %s kept failing", booking_id)
                    # Raise the generic exception and leave the booking active
                    raise ProcessingException("Refund could not be completed")
                # Count this retry before the next attempt
                retries += 1
            except PermanentGatewayException:
                # Log the permanent refusal before recording it
                logger.error("Refund for booking %s refused permanently; booking stays active", booking_id)
                # Record the refused refund while keeping the booking active
                booking.refund_status = RefundStatus.FAILED
                # Return the still-active booking so the client sees the refund outcome
                return booking
            except GatewayUnavailableException:
                # Log the unavailability before raising it
                logger.error("Cancellation rejected: payment gateway unavailable for booking %s", booking_id)
                # Raise the generic exception and leave the booking active
                raise ProcessingException("Payment gateway unavailable")
            except Exception:
                # Log the unexpected gateway failure before wrapping it
                logger.exception("Cancellation rejected: unexpected gateway error for booking %s", booking_id)
                # Raise the generic exception and leave the booking active
                raise ProcessingException("Payment gateway failed")
        # Mark the booking cancelled so its seat is released
        booking.status = BookingStatus.CANCELLED
        # Record that the gateway confirmed the refund
        booking.refund_status = RefundStatus.REFUNDED
        # Return the cancelled booking to the caller
        return booking

    # Return the refund status of a booking, rejecting unknown booking identifiers
    def get_refund_status(self, booking_id):
        # Look up the booking whose refund status is requested
        booking = self._bookings.get(booking_id)
        # Check whether the booking exists
        if booking is None:
            # Log the rejection before raising it
            logger.error("Refund status lookup rejected: unknown booking %s", booking_id)
            # Raise the generic exception for an unknown booking
            raise ProcessingException("Unknown booking")
        # Return the refund status recorded on the booking
        return booking.refund_status
