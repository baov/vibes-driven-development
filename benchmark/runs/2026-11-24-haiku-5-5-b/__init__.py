# Standard logging module, used to record every exception before it is rethrown.
import logging
# Dataclass decorator that generates the plain-data entities below.
from dataclasses import dataclass
# Screening start times are datetimes; the cancellation cut-off is a timedelta.
from datetime import datetime, timedelta

# Module logger shared by BookingManager so every failure is recorded in one place.
logger = logging.getLogger(__name__)

# Booking status for a booking that currently holds its seat.
ACTIVE = "ACTIVE"
# Booking status for a booking whose seat has been released.
CANCELLED = "CANCELLED"
# Refund status before any refund has been attempted.
NOT_REQUESTED = "NOT_REQUESTED"
# Refund status once the payment gateway has accepted the refund.
REFUNDED = "REFUNDED"
# Refund status once the gateway failed permanently or transient retries ran out.
FAILED = "FAILED"
# Number of retries allowed after the first transient refund failure.
MAX_TRANSIENT_RETRIES = 3
# Clients may cancel only when at least this much time remains before the start.
CANCELLATION_CUTOFF = timedelta(hours=2)


# Generic wrapper raised at the service boundary so gateway details do not leak to callers.
class ProcessingException(Exception):
    # No extra state; the message alone describes the failure.
    pass


# Raised when a business rule rejects a request, such as a seat already being booked.
class BookingRejectedException(Exception):
    # No extra state; the message names the rule that was violated.
    pass


# Raised by a payment gateway when a refund failed but a retry may succeed.
class TransientRefundException(Exception):
    # No extra state; the failure is described by the exception type itself.
    pass


# Raised by a payment gateway when a refund failed and will never succeed.
class PermanentRefundException(Exception):
    # No extra state; the failure is described by the exception type itself.
    pass


# Raised by a payment gateway when it cannot process refunds at all right now.
class GatewayUnavailableException(Exception):
    # No extra state; the failure is described by the exception type itself.
    pass


# Plain data describing one screening: its start, the room layout and the ticket price.
@dataclass
class Screening:
    # Identifier clients use to refer to this screening.
    screening_id: str
    # Moment the screening starts.
    start_time: datetime
    # Number of rows in the room, numbered from 1.
    rows: int
    # Number of seats in each row, numbered from 1.
    seats_per_row: int
    # Ticket price, which is also the amount refunded on cancellation.
    price: float


# Plain data describing one seat booking and its cancellation state.
@dataclass
class Booking:
    # Identifier returned to the client when the seat is booked.
    booking_id: str
    # Screening the seat belongs to.
    screening_id: str
    # Row of the booked seat.
    row: int
    # Seat number within the row.
    seat: int
    # Whether the booking still holds the seat (ACTIVE) or was cancelled.
    status: str = ACTIVE
    # Outcome of the refund for this booking: NOT_REQUESTED, REFUNDED or FAILED.
    refund_status: str = NOT_REQUESTED


# Service that owns screenings and bookings and drives refunds through an injected payment gateway.
class BookingManager:
    # Stores the payment gateway collaborator and starts with no screenings or bookings.
    def __init__(self, payment_gateway):
        # Gateway the manager calls to refund cancelled bookings.
        self.payment_gateway = payment_gateway
        # Registered screenings keyed by screening_id.
        self.screenings = {}
        # Bookings keyed by booking_id.
        self.bookings = {}

    # Registers a screening so that seats can be booked for it.
    def add_screening(self, screening):
        # Store the screening under its identifier.
        self.screenings[screening.screening_id] = screening

    # Books one seat for a screening and returns the new booking identifier.
    def book_seat(self, screening_id, row, seat):
        # Look up the screening the client wants to book.
        screening = self.screenings.get(screening_id)
        # Check whether the screening is known.
        if screening is None:
            # Record the rejection before raising it.
            logger.warning("Rejected booking: unknown screening %s", screening_id)
            # Refuse the booking because there is no such screening.
            raise BookingRejectedException("unknown screening")
        # Check whether the requested seat exists in the room layout.
        if not (1 <= row <= screening.rows and 1 <= seat <= screening.seats_per_row):
            # Record the rejection before raising it.
            logger.warning("Rejected booking: seat %s/%s outside layout of %s", row, seat, screening_id)
            # Refuse the booking because the seat is outside the room.
            raise BookingRejectedException("seat outside room layout")
        # Go through every booking to find an active one on the same seat.
        for booking in self.bookings.values():
            # Compare the candidate seat with this booking, ignoring cancelled ones.
            if booking.screening_id == screening_id and booking.row == row and booking.seat == seat and booking.status == ACTIVE:
                # Record the rejection before raising it.
                logger.warning("Rejected booking: seat %s/%s already booked for %s", row, seat, screening_id)
                # Refuse the booking because the seat is already held.
                raise BookingRejectedException("seat already booked")
        # Derive a new identifier from the number of bookings made so far.
        booking_id = str(len(self.bookings) + 1)
        # Record the new active booking.
        self.bookings[booking_id] = Booking(booking_id, screening_id, row, seat)
        # Return the identifier so the client can cancel the booking later.
        return booking_id

    # Cancels an active booking up to the cut-off and refunds the ticket price through the gateway.
    def cancel_booking(self, booking_id, now):
        # Look up the booking the client wants to cancel.
        booking = self.bookings.get(booking_id)
        # Check whether the booking exists.
        if booking is None:
            # Record the rejection before raising it.
            logger.warning("Rejected cancellation: unknown booking %s", booking_id)
            # Refuse the cancellation because there is no such booking.
            raise BookingRejectedException("unknown booking")
        # Check whether the booking was already cancelled.
        if booking.status == CANCELLED:
            # Record the rejection before raising it.
            logger.warning("Rejected cancellation: booking %s already cancelled", booking_id)
            # Refuse the cancellation because it was already done.
            raise BookingRejectedException("booking already cancelled")
        # Find the screening to read its start time and refund amount.
        screening = self.screenings[booking.screening_id]
        # Check whether the cancellation is still allowed under the cut-off.
        if screening.start_time - now < CANCELLATION_CUTOFF:
            # Record the rejection before raising it.
            logger.warning("Rejected cancellation: booking %s is inside the cut-off", booking_id)
            # Refuse the cancellation because the screening starts too soon.
            raise BookingRejectedException("cancellation window closed")
        # Count the transient retries already spent on this refund.
        retries = 0
        # Attempt the refund until the gateway accepts it or a failure is final.
        while True:
            # Guard the gateway call so its failures can be logged and classified.
            try:
                # Ask the gateway to refund the ticket price for this booking.
                self.payment_gateway.refund(booking_id, screening.price)
                # Leave the retry loop because the refund was accepted.
                break
            # Handle a transient failure, which may succeed on retry.
            except TransientRefundException as error:
                # Log the transient failure before deciding whether to retry.
                logger.error("Transient refund failure for booking %s: %s", booking_id, error)
                # Check whether the allowed retries have all been used.
                if retries == MAX_TRANSIENT_RETRIES:
                    # Mark the refund as failed because it will not be retried further.
                    booking.refund_status = FAILED
                    # Log the wrapper before raising it to the caller.
                    logger.error("Refund for booking %s failed after %s retries", booking_id, retries)
                    # Surface the failure as a generic processing error; the booking stays active.
                    raise ProcessingException("refund failed after retries")
                # Count this retry before attempting the refund again.
                retries += 1
            # Handle a permanent failure, which no retry can fix.
            except PermanentRefundException as error:
                # Log the permanent failure with its details.
                logger.error("Permanent refund failure for booking %s: %s", booking_id, error)
                # Mark the refund as failed so the client can see the outcome.
                booking.refund_status = FAILED
                # Log the wrapper before raising it to the caller.
                logger.error("Cancellation of booking %s rejected: refund failed permanently", booking_id)
                # Surface the failure as a generic processing error; the booking stays active.
                raise ProcessingException("refund failed permanently")
            # Handle an unavailable gateway, which rejects the cancellation outright.
            except GatewayUnavailableException as error:
                # Log the unavailability with its details.
                logger.error("Gateway unavailable for booking %s: %s", booking_id, error)
                # Log the wrapper before raising it to the caller; the refund status is left unchanged.
                logger.error("Cancellation of booking %s rejected: gateway unavailable", booking_id)
                # Surface the failure as a generic processing error; the booking stays active.
                raise ProcessingException("refund gateway unavailable")
        # Release the seat now that the refund has been accepted.
        booking.status = CANCELLED
        # Record that the refund was accepted.
        booking.refund_status = REFUNDED

    # Returns the refund status of a booking so clients can see how its refund went.
    def get_refund_status(self, booking_id):
        # Look up the booking whose refund status is requested.
        booking = self.bookings.get(booking_id)
        # Check whether the booking exists.
        if booking is None:
            # Record the rejection before raising it.
            logger.warning("Rejected refund status request: unknown booking %s", booking_id)
            # Refuse the request because there is no such booking.
            raise BookingRejectedException("unknown booking")
        # Return the current refund status of the booking.
        return booking.refund_status
