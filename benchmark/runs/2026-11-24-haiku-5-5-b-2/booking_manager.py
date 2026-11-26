# Import dataclass to declare the plain data structures of this module.
from dataclasses import dataclass
# Import datetime and timedelta for screening times and the cancellation cut-off.
from datetime import datetime, timedelta
# Import itertools to hand out sequential booking ids.
import itertools
# Import logging so every layer can record the exceptions it sees.
import logging

# Logger shared by the classes in this module.
logger = logging.getLogger(__name__)

# Status of a booking that holds its seat.
ACTIVE = "active"
# Status of a booking that has been cancelled and released its seat.
CANCELLED = "cancelled"
# Refund status before any refund has been completed.
REFUND_NONE = "none"
# Refund status once the payment gateway accepted the refund.
REFUND_REFUNDED = "refunded"
# Refund status once the refund was refused for good or the retries ran out.
REFUND_FAILED = "failed"
# A booking can only be cancelled at least this long before its screening starts.
CANCELLATION_CUTOFF = timedelta(hours=2)
# One initial refund attempt plus up to three retries for transient failures.
MAX_REFUND_ATTEMPTS = 4


# A room laid out as rows of seats, numbered from 1.
@dataclass
class Room:
    # Number of rows in the room.
    rows: int
    # Number of seats in each row.
    seats_per_row: int


# A screening of a film: when it starts, in which room, and its ticket price.
@dataclass
class Screening:
    # Unique identifier of the screening.
    screening_id: str
    # Moment the screening starts.
    start_time: datetime
    # Room in which the screening takes place.
    room: Room
    # Ticket price, refunded in full when a booking is cancelled.
    price: float


# A client's reservation of one seat for one screening.
@dataclass
class Booking:
    # Unique identifier of the booking.
    booking_id: int
    # Screening the seat was booked for.
    screening: Screening
    # Row of the booked seat.
    row: int
    # Number of the booked seat within its row.
    seat: int
    # Client who made the booking.
    client_id: str
    # Whether the booking still holds its seat.
    status: str = ACTIVE
    # Outcome of the refund attempts made for this booking.
    refund_status: str = REFUND_NONE


# Generic exception raised at the booking boundary, hiding the lower-level cause.
class ProcessingException(Exception):
    pass


# Raised by a payment gateway when a refund fails temporarily and may be retried.
class TransientPaymentError(Exception):
    pass


# Raised by a payment gateway when a refund is refused and must not be retried.
class PermanentPaymentError(Exception):
    pass


# Raised by a payment gateway when it cannot be reached at all.
class PaymentGatewayUnavailableError(Exception):
    pass


# Owns the bookings in memory and enforces the booking, cancellation and refund rules.
class BookingManager:
    # Store the payment gateway used for refunds and start with no bookings.
    def __init__(self, payment_gateway):
        # Keep the gateway so cancellations can refund through it.
        self._payment_gateway = payment_gateway
        # Index of every booking ever made, keyed by booking id.
        self._bookings = {}
        # Source of sequential booking ids, starting at 1.
        self._booking_ids = itertools.count(1)

    # Book one seat for a screening, rejecting seats outside the room or already held.
    def book_seat(self, screening, row, seat, client_id):
        # Check the requested seat exists in the room before touching any state.
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            # Log the rejected request so it is visible in the logs.
            logger.error("Seat %s/%s does not exist in screening %s", row, seat, screening.screening_id)
            # Reject the request with the generic exception.
            raise ProcessingException("Seat does not exist in this room")
        # Check whether an active booking already holds this seat for this screening.
        seat_taken = any(
            b.screening.screening_id == screening.screening_id and b.row == row and b.seat == seat and b.status == ACTIVE
            for b in self._bookings.values()
        )
        # Reject the request when the seat is already booked.
        if seat_taken:
            # Log the rejected request so it is visible in the logs.
            logger.error("Seat %s/%s is already booked in screening %s", row, seat, screening.screening_id)
            # Reject the request with the generic exception.
            raise ProcessingException("Seat is already booked")
        # Create the booking with the next free id.
        booking = Booking(booking_id=next(self._booking_ids), screening=screening, row=row, seat=seat, client_id=client_id)
        # Store the booking so later cancellations and seat checks can find it.
        self._bookings[booking.booking_id] = booking
        # Return the new booking to the caller.
        return booking

    # Cancel an active booking and refund its price, rejecting unknown, cancelled or too-late bookings.
    def cancel_booking(self, booking_id, now):
        # Look the booking up by id; None means it does not exist.
        booking = self._bookings.get(booking_id)
        # Reject cancellation of a booking that does not exist.
        if booking is None:
            # Log the rejected request so it is visible in the logs.
            logger.error("Cannot cancel unknown booking %s", booking_id)
            # Reject the request with the generic exception.
            raise ProcessingException("Unknown booking")
        # Reject cancellation of a booking that has already been cancelled.
        if booking.status != ACTIVE:
            # Log the rejected request so it is visible in the logs.
            logger.error("Booking %s is already cancelled", booking_id)
            # Reject the request with the generic exception.
            raise ProcessingException("Booking is already cancelled")
        # Reject cancellation when less than the cut-off remains before the screening starts.
        if now > booking.screening.start_time - CANCELLATION_CUTOFF:
            # Log the rejected request so it is visible in the logs.
            logger.error("Booking %s is too close to its screening to be cancelled", booking_id)
            # Reject the request with the generic exception.
            raise ProcessingException("Booking can no longer be cancelled")
        # Assume the refund has not succeeded until the gateway confirms it.
        refunded = False
        # Attempt the refund up to MAX_REFUND_ATTEMPTS times while the failures are transient.
        for attempt in range(1, MAX_REFUND_ATTEMPTS + 1):
            # Try the refund and handle each gateway outcome on its own.
            try:
                # Ask the gateway to refund the screening price for this booking.
                self._payment_gateway.refund(booking_id, booking.screening.price)
                # Record that the gateway accepted the refund.
                refunded = True
                # Stop retrying because the refund is complete.
                break
            # Handle a transient failure by logging it so the loop retries.
            except TransientPaymentError:
                # Log the transient failure with its traceback.
                logger.exception("Refund attempt %s for booking %s failed transiently", attempt, booking_id)
            # Handle a permanent refusal by logging it and stopping without retrying.
            except PermanentPaymentError:
                # Log the refusal with its traceback.
                logger.exception("Refund for booking %s was refused permanently", booking_id)
                # Stop retrying because the gateway will not accept this refund.
                break
            # Handle an unreachable gateway by logging it and rejecting the cancellation.
            except PaymentGatewayUnavailableError:
                # Log the unavailability with its traceback.
                logger.exception("Refund gateway unavailable for booking %s", booking_id)
                # Reject the cancellation with the generic exception, leaving the booking active.
                raise ProcessingException("Refund gateway unavailable, cancellation rejected")
        # Check whether the gateway confirmed the refund.
        if refunded:
            # Record that the price was refunded.
            booking.refund_status = REFUND_REFUNDED
            # Release the seat by marking the booking as cancelled.
            booking.status = CANCELLED
        # Handle the case where the refund was not completed.
        else:
            # Record the failed refund and keep the booking active so the cancellation can be retried.
            booking.refund_status = REFUND_FAILED
        # Return the updated booking to the caller.
        return booking

    # Return the refund status of a booking, rejecting unknown ids.
    def get_refund_status(self, booking_id):
        # Look the booking up by id; None means it does not exist.
        booking = self._bookings.get(booking_id)
        # Reject the request when the booking does not exist.
        if booking is None:
            # Log the rejected request so it is visible in the logs.
            logger.error("Cannot read refund status of unknown booking %s", booking_id)
            # Reject the request with the generic exception.
            raise ProcessingException("Unknown booking")
        # Return the refund status recorded on the booking.
        return booking.refund_status
