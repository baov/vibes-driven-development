# Standard library logging, used so every layer can record the exceptions it sees.
import logging
# Dataclasses for the plain data entities (Room, Screening, Booking).
from dataclasses import dataclass
# Time types for screening start times and the cancellation cutoff.
from datetime import datetime, timedelta
# Sequential source of booking ids.
from itertools import count

# Module logger shared by every class in this module.
logger = logging.getLogger(__name__)

# Minimum lead time before the screening starts for a cancellation to be accepted.
CANCELLATION_CUTOFF = timedelta(hours=2)

# Number of retries after the first refund attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3


# Wraps lower-level failures so callers never see implementation details.
class ProcessingException(Exception):
    # Carries only the message; the original cause is omitted by design.
    pass


# Raised by a payment gateway when a refund failed but may succeed if retried.
class TransientGatewayError(Exception):
    # Marker exception; no extra state.
    pass


# Raised by a payment gateway when a refund failed permanently.
class PermanentGatewayError(Exception):
    # Marker exception; no extra state.
    pass


# Raised by a payment gateway when it cannot be reached or is not serving requests.
class GatewayUnavailableError(Exception):
    # Marker exception; no extra state.
    pass


# Physical layout of a screening room.
@dataclass
class Room:
    # Number of rows in the room, numbered from 1.
    rows: int
    # Number of seats in each row, numbered from 1.
    seats_per_row: int


# A showing of a film at a fixed start time and price.
@dataclass
class Screening:
    # Unique identifier of the screening.
    screening_id: str
    # When the screening starts.
    start_time: datetime
    # Layout of the room hosting the screening.
    room: Room
    # Ticket price in minor currency units (e.g. cents), so amounts are exact integers.
    price_cents: int


# A client's reservation of one seat for one screening.
@dataclass
class Booking:
    # Unique identifier of the booking.
    booking_id: str
    # Screening the seat belongs to.
    screening_id: str
    # Row of the booked seat.
    row: int
    # Seat number within the row.
    seat: int
    # Either "active" or "cancelled".
    status: str = "active"
    # Either "none", "refunded" or "failed".
    refund_status: str = "none"


# Contract for the payment gateway used to refund cancelled bookings.
class PaymentGateway:
    # Refunds amount_cents for the booking; raises one of the gateway errors on failure.
    def refund(self, booking_id, amount_cents):
        # Subclasses must provide the real refund call.
        raise NotImplementedError


# Books seats and cancels bookings, delegating refunds to the payment gateway.
class BookingManager:
    # Receives the gateway and a clock (a callable returning the current time) for testability.
    def __init__(self, gateway, clock=datetime.now):
        # Gateway used to issue refunds.
        self.gateway = gateway
        # Source of the current time, used for the cancellation cutoff.
        self.clock = clock
        # Known screenings keyed by screening_id.
        self.screenings = {}
        # All bookings keyed by booking_id.
        self.bookings = {}
        # Sequence used to generate new booking ids.
        self.booking_ids = count(1)

    # Registers a screening so that seats can be booked for it.
    def add_screening(self, screening):
        # Store the screening under its id.
        self.screenings[screening.screening_id] = screening

    # Books a seat for a screening; rejects unknown screenings, seats outside the room and seats already booked.
    def book_seat(self, screening_id, row, seat):
        # Look up the screening the client wants.
        data = self.screenings.get(screening_id)
        # Reject the request when the screening does not exist.
        if data is None:
            # Log the rejection before raising it.
            logger.error("book_seat rejected: unknown screening %s", screening_id)
            # Raise the processing failure to the caller.
            raise ProcessingException(f"unknown screening {screening_id}")
        # Reject the request when the seat is outside the room layout.
        if not (1 <= row <= data.room.rows and 1 <= seat <= data.room.seats_per_row):
            # Log the rejection before raising it.
            logger.error("book_seat rejected: seat %s-%s outside room of screening %s", row, seat, screening_id)
            # Raise the processing failure to the caller.
            raise ProcessingException(f"seat {row}-{seat} does not exist in screening {screening_id}")
        # Scan existing bookings to see whether an active one already holds this seat.
        for info in self.bookings.values():
            # Check whether this booking is an active reservation of the same seat.
            if info.screening_id == screening_id and info.row == row and info.seat == seat and info.status == "active":
                # Log the rejection before raising it.
                logger.error("book_seat rejected: seat %s-%s already booked for %s", row, seat, screening_id)
                # Raise the processing failure to the caller.
                raise ProcessingException(f"seat {row}-{seat} already booked for screening {screening_id}")
        # Create the new active booking with the next sequential id.
        result = Booking(f"B{next(self.booking_ids)}", screening_id, row, seat)
        # Store the booking so it can be cancelled or queried later.
        self.bookings[result.booking_id] = result
        # Return the booking to the caller.
        return result

    # Cancels an active booking that is at least CANCELLATION_CUTOFF before its screening, and refunds it.
    def cancel_booking(self, booking_id):
        # Look up the booking to cancel.
        data = self.bookings.get(booking_id)
        # Reject the request when the booking does not exist.
        if data is None:
            # Log the rejection before raising it.
            logger.error("cancel_booking rejected: unknown booking %s", booking_id)
            # Raise the processing failure to the caller.
            raise ProcessingException(f"unknown booking {booking_id}")
        # Reject the request when the booking is no longer active.
        if data.status != "active":
            # Log the rejection before raising it.
            logger.error("cancel_booking rejected: booking %s already cancelled", booking_id)
            # Raise the processing failure to the caller.
            raise ProcessingException(f"booking {booking_id} already cancelled")
        # Look up the screening to compare its start time and read its price.
        info = self.screenings[data.screening_id]
        # Reject the request when the cutoff before the screening has already passed.
        if self.clock() > info.start_time - CANCELLATION_CUTOFF:
            # Log the rejection before raising it.
            logger.error("cancel_booking rejected: booking %s is inside the cancellation cutoff", booking_id)
            # Raise the processing failure to the caller.
            raise ProcessingException(f"booking {booking_id} is within the cancellation cutoff")
        # Track whether the gateway accepted the refund.
        refunded = False
        # Make the first refund attempt plus up to MAX_REFUND_RETRIES retries.
        for attempt in range(MAX_REFUND_RETRIES + 1):
            # Try to refund the booking through the gateway.
            try:
                # Issue the refund for the screening price.
                self.gateway.refund(booking_id, info.price_cents)
                # Record that the refund succeeded.
                refunded = True
                # Stop retrying once the refund has gone through.
                break
            # Handle a transient gateway failure by trying again.
            except TransientGatewayError:
                # Log the transient failure with the attempt number before retrying.
                logger.warning("refund for booking %s failed transiently on attempt %s", booking_id, attempt + 1)
            # Handle a permanent gateway failure by giving up without retrying.
            except PermanentGatewayError:
                # Log the permanent failure before giving up.
                logger.error("refund for booking %s failed permanently", booking_id)
                # Stop retrying because the gateway will not accept this refund.
                break
            # Handle an unavailable gateway by rejecting the cancellation.
            except GatewayUnavailableError:
                # Log the unavailability before rejecting the cancellation.
                logger.error("refund gateway unavailable for booking %s", booking_id)
                # Raise the processing failure to the caller; the booking stays active.
                raise ProcessingException(f"refund gateway unavailable for booking {booking_id}")
        # Apply the outcome when the refund went through.
        if refunded:
            # Mark the booking as cancelled.
            data.status = "cancelled"
            # Record the successful refund.
            data.refund_status = "refunded"
        # Apply the outcome when the refund did not go through.
        else:
            # Log that the booking remains active because the refund failed.
            logger.warning("refund for booking %s not completed; booking remains active", booking_id)
            # Record the failed refund while leaving the booking active.
            data.refund_status = "failed"
        # Return the updated booking to the caller.
        return data

    # Returns the refund status of a booking; rejects unknown bookings.
    def get_refund_status(self, booking_id):
        # Look up the booking whose refund status is requested.
        data = self.bookings.get(booking_id)
        # Reject the request when the booking does not exist.
        if data is None:
            # Log the rejection before raising it.
            logger.error("get_refund_status rejected: unknown booking %s", booking_id)
            # Raise the processing failure to the caller.
            raise ProcessingException(f"unknown booking {booking_id}")
        # Return the refund status recorded on the booking.
        return data.refund_status
