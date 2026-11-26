# Import the standard logging module so every rejection and gateway failure can be recorded.
import logging
# Import uuid to generate collision-free booking identifiers.
import uuid
# Import dataclass to declare the plain data classes for rooms, screenings and bookings.
from dataclasses import dataclass
# Import datetime and timedelta for start times and the cancellation cutoff.
from datetime import datetime, timedelta
# Import Callable and Dict for the clock and screening registry type hints.
from typing import Callable, Dict

# Logger for this module; every rejection and gateway failure is logged through it.
logger = logging.getLogger(__name__)
# Clients may cancel a booking only up to this long before the screening starts.
CANCELLATION_CUTOFF = timedelta(hours=2)
# One initial refund attempt plus up to three retries.
MAX_REFUND_ATTEMPTS = 4
# Booking status while the seat is held.
ACTIVE = "active"
# Booking status once the cancellation has been accepted and refunded.
CANCELLED = "cancelled"
# Refund status before any refund succeeded or failed.
REFUND_NONE = "none"
# Refund status after the gateway accepted the refund.
REFUND_REFUNDED = "refunded"
# Refund status after a permanent failure or after transient retries ran out.
REFUND_FAILED = "failed"


# Generic exception raised at the service boundary so lower-level details do not leak to clients.
class ProcessingException(Exception):
    # The class body only declares the type; the message carries the reason.
    pass


# Gateway failure that may succeed if the refund is attempted again.
class GatewayTransientError(Exception):
    # The class body only declares the type; the gateway signals meaning through it.
    pass


# Gateway failure that will not succeed on retry; the refund is refused for good.
class GatewayPermanentError(Exception):
    # The class body only declares the type; the gateway signals meaning through it.
    pass


# Gateway outage; the refund cannot be attempted at all right now.
class GatewayUnavailableError(Exception):
    # The class body only declares the type; the gateway signals meaning through it.
    pass


# A room is a grid of rows and seats per row; rows and seats are numbered from 1.
@dataclass
class Room:
    # Number of rows in the room.
    rows: int
    # Number of seats in each row.
    seats_per_row: int


# A screening has a start time, a room and a price.
@dataclass
class Screening:
    # Start time of the screening.
    start: datetime
    # Room where the screening takes place.
    room: Room
    # Ticket price in cents, so the amount stays an exact integer.
    price_cents: int


# A booking holds one seat of one screening for a client.
@dataclass
class Booking:
    # Unique identifier of the booking.
    booking_id: str
    # Identifier of the screening the seat belongs to.
    screening_id: str
    # Row of the booked seat.
    row: int
    # Seat number within the row.
    seat: int
    # ACTIVE while the seat is held, CANCELLED afterwards.
    status: str = ACTIVE
    # REFUND_NONE, REFUND_REFUNDED or REFUND_FAILED.
    refund_status: str = REFUND_NONE


# Books seats for screenings and cancels bookings, refunding through the injected payment gateway.
class BookingManager:
    # Store the screenings, the payment gateway and the clock used for the cancellation cutoff.
    def __init__(self, screenings: Dict[str, Screening], gateway, clock: Callable[[], datetime]):
        # Known screenings keyed by identifier.
        self._screenings = screenings
        # Payment gateway exposing refund(booking_id, amount_cents).
        self._gateway = gateway
        # Callable returning the current time.
        self._clock = clock
        # All bookings keyed by identifier, including cancelled ones.
        self._bookings: Dict[str, Booking] = {}

    # Reserve a seat for a screening; reject unknown screenings, seats outside the room and seats already held.
    def book_seat(self, screening_id: str, row: int, seat: int) -> str:
        # Look up the screening the client wants to book.
        screening = self._screenings.get(screening_id)
        # Reject the request when the screening does not exist.
        if screening is None:
            # Build the reason shown in the log and the exception.
            message = f"Unknown screening {screening_id}"
            # Record the rejection in the log.
            logger.warning(message)
            # Raise the generic exception to the caller.
            raise ProcessingException(message)
        # Reject seats outside the grid of the screening's room.
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            # Build the reason naming the missing seat.
            message = f"Seat {row}-{seat} does not exist in screening {screening_id}"
            # Record the rejection in the log.
            logger.warning(message)
            # Raise the generic exception to the caller.
            raise ProcessingException(message)
        # Check every booking for an active hold on the same seat.
        for booking in self._bookings.values():
            # Only active bookings hold a seat; cancelled ones release it again.
            if booking.status != ACTIVE:
                # Skip bookings that no longer hold a seat.
                continue
            # Compare the screening and seat of the active booking with the request.
            if booking.screening_id == screening_id and booking.row == row and booking.seat == seat:
                # Build the reason naming the taken seat.
                message = f"Seat {row}-{seat} is already booked for screening {screening_id}"
                # Record the rejection in the log.
                logger.warning(message)
                # Raise the generic exception to the caller.
                raise ProcessingException(message)
        # Generate a new unique identifier for the booking.
        booking_id = uuid.uuid4().hex
        # Store the new active booking.
        self._bookings[booking_id] = Booking(booking_id, screening_id, row, seat)
        # Return the identifier so the client can cancel or query the booking later.
        return booking_id

    # Cancel an active booking up to the cutoff and refund its price; retry transient gateway failures.
    def cancel_booking(self, booking_id: str) -> None:
        # Look up the booking the client wants to cancel.
        booking = self._bookings.get(booking_id)
        # Reject the request when the booking does not exist.
        if booking is None:
            # Build the reason shown in the log and the exception.
            message = f"Unknown booking {booking_id}"
            # Record the rejection in the log.
            logger.warning(message)
            # Raise the generic exception to the caller.
            raise ProcessingException(message)
        # Reject the request when the booking was already cancelled.
        if booking.status == CANCELLED:
            # Build the reason shown in the log and the exception.
            message = f"Booking {booking_id} is already cancelled"
            # Record the rejection in the log.
            logger.warning(message)
            # Raise the generic exception to the caller.
            raise ProcessingException(message)
        # Look up the screening of the booking to get its start time and price.
        screening = self._screenings[booking.screening_id]
        # Compute the latest moment at which cancellation is still allowed.
        deadline = screening.start - CANCELLATION_CUTOFF
        # Reject the request when the cutoff has already passed.
        if self._clock() > deadline:
            # Build the reason shown in the log and the exception.
            message = f"Booking {booking_id} can no longer be cancelled"
            # Record the rejection in the log.
            logger.warning(message)
            # Raise the generic exception to the caller.
            raise ProcessingException(message)
        # Attempt the refund, retrying only transient failures up to the attempt limit.
        for attempt in range(1, MAX_REFUND_ATTEMPTS + 1):
            # Guard the gateway call so each gateway failure type is handled explicitly.
            try:
                # Ask the gateway to refund the screening price, keyed by the booking identifier.
                self._gateway.refund(booking_id, screening.price_cents)
            # Handle a transient failure by retrying, unless the attempts are exhausted.
            except GatewayTransientError:
                # Log the transient failure with its traceback before deciding what to do.
                logger.exception(f"Transient refund failure for booking {booking_id} on attempt {attempt}")
                # Retry while attempts remain.
                if attempt < MAX_REFUND_ATTEMPTS:
                    # Move on to the next attempt.
                    continue
                # Record the failed refund on the booking; the booking stays active.
                booking.refund_status = REFUND_FAILED
                # Build the reason shown in the exception after retries ran out.
                message = f"Refund for booking {booking_id} failed after {MAX_REFUND_ATTEMPTS} attempts"
                # Raise the generic exception to the caller.
                raise ProcessingException(message)
            # Handle a permanent failure by recording it; the booking stays active.
            except GatewayPermanentError:
                # Log the permanent failure with its traceback.
                logger.exception(f"Permanent refund failure for booking {booking_id}")
                # Record the failed refund on the booking; the booking stays active.
                booking.refund_status = REFUND_FAILED
                # Build the reason shown in the exception.
                message = f"Refund for booking {booking_id} was refused permanently"
                # Raise the generic exception to the caller.
                raise ProcessingException(message)
            # Handle an unavailable gateway by rejecting the cancellation without touching the booking.
            except GatewayUnavailableError:
                # Log the outage with its traceback.
                logger.exception(f"Refund gateway unavailable for booking {booking_id}")
                # Build the reason shown in the exception.
                message = f"Cancellation of booking {booking_id} rejected: refund gateway unavailable"
                # Raise the generic exception to the caller.
                raise ProcessingException(message)
            # Reach this line only when the refund succeeded: release the seat and record the refund.
            booking.status = CANCELLED
            # Record that the refund was accepted by the gateway.
            booking.refund_status = REFUND_REFUNDED
            # Stop once the cancellation is complete.
            return

    # Expose the refund status of a booking; reject unknown bookings.
    def get_refund_status(self, booking_id: str) -> str:
        # Look up the booking whose refund status is requested.
        booking = self._bookings.get(booking_id)
        # Reject the request when the booking does not exist.
        if booking is None:
            # Build the reason shown in the log and the exception.
            message = f"Unknown booking {booking_id}"
            # Record the rejection in the log.
            logger.warning(message)
            # Raise the generic exception to the caller.
            raise ProcessingException(message)
        # Return the refund status recorded on the booking.
        return booking.refund_status
