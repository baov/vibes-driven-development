# Standard library logging, used at every layer boundary.
import logging
# Plain data classes for the entities.
from dataclasses import dataclass
# Timestamps for screenings and the cancellation cut-off.
from datetime import datetime, timedelta, timezone
# Enumerations for booking and refund states.
from enum import Enum


# Generic exception raised by the service; hides gateway details from callers.
class ProcessingException(Exception):
    # No extra behaviour; the message carries the reason.
    pass


# Raised by a gateway when a refund failed but may succeed if retried.
class GatewayTransientError(Exception):
    # No extra behaviour; the type alone carries the meaning.
    pass


# Raised by a gateway when a refund is refused and must not be retried.
class GatewayPermanentError(Exception):
    # No extra behaviour; the type alone carries the meaning.
    pass


# Raised by a gateway when it cannot be reached at all.
class GatewayUnavailableError(Exception):
    # No extra behaviour; the type alone carries the meaning.
    pass


# Lifecycle states of a booking.
class BookingStatus(Enum):
    # The seat is held for the client.
    ACTIVE = "active"
    # The booking was cancelled and its seat released.
    CANCELLED = "cancelled"


# Outcome of the refund attached to a booking.
class RefundStatus(Enum):
    # No refund has been completed or attempted yet.
    NOT_REQUESTED = "not_requested"
    # The gateway accepted the refund.
    REFUNDED = "refunded"
    # The refund failed permanently or exhausted its retries.
    FAILED = "failed"


# Rows and seats of the room hosting a screening.
@dataclass
class Room:
    # Number of rows, numbered from 1.
    rows: int
    # Number of seats per row, numbered from 1.
    seats_per_row: int


# A showing at a given time in a room, at a given price.
@dataclass
class Screening:
    # Identifier of the screening.
    screening_id: str
    # Timezone-aware start time of the screening.
    start_time: datetime
    # Room hosting the screening.
    room: Room
    # Ticket price in cents, avoiding floating-point rounding.
    price_cents: int


# A seat reserved by a client for a screening.
@dataclass
class Booking:
    # Identifier of the booking.
    booking_id: int
    # Client who holds the booking.
    client_id: str
    # Screening the seat is reserved for.
    screening_id: str
    # Row of the reserved seat.
    row: int
    # Seat number within the row.
    seat: int
    # Whether the booking is still active.
    status: BookingStatus = BookingStatus.ACTIVE
    # Outcome of the latest refund attempt.
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# Books seats, cancels bookings with refunds, and reports booking and refund state.
class BookingManager:
    # Number of retries allowed after a transient refund failure.
    MAX_REFUND_RETRIES = 3
    # Cancellations are rejected once less than this remains before the start.
    CANCELLATION_CUTOFF = timedelta(hours=2)

    # Stores the gateway and the clock; the clock defaults to real UTC time.
    def __init__(self, gateway, clock=None):
        # Payment gateway used to issue refunds.
        self._gateway = gateway
        # Source of the current time, injectable for tests.
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Known screenings keyed by screening id.
        self._screenings = {}
        # Bookings keyed by booking id.
        self._bookings = {}
        # Id given to the next booking.
        self._next_booking_id = 1
        # Logger for this service layer.
        self._logger = logging.getLogger(__name__)

    # Registers a screening so that seats can be booked for it.
    def add_screening(self, screening):
        # Store the screening under its id.
        self._screenings[screening.screening_id] = screening

    # Reserves a seat for a client; rejects unknown screenings, nonexistent seats and seats already held.
    def book_seat(self, client_id, screening_id, row, seat):
        # Look up the screening the client wants.
        screening = self._screenings.get(screening_id)
        # Reject a screening that was never registered.
        if screening is None:
            # Message describing the rejection.
            message = f"unknown screening {screening_id}"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Reject seats outside the room's rows and seats.
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            # Message describing the rejection.
            message = f"seat {row}-{seat} does not exist in screening {screening_id}"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Scan existing bookings for an active hold on the same seat.
        for booking in self._bookings.values():
            # Detect an active booking of the requested seat.
            if booking.screening_id == screening_id and booking.row == row and booking.seat == seat and booking.status is BookingStatus.ACTIVE:
                # Message describing the rejection.
                message = f"seat {row}-{seat} already booked for screening {screening_id}"
                # Log the rejection before raising it.
                self._logger.warning(message)
                # Raise the generic service exception.
                raise ProcessingException(message)
        # Create the booking with the next free id.
        booking = Booking(booking_id=self._next_booking_id, client_id=client_id, screening_id=screening_id, row=row, seat=seat)
        # Advance the id counter.
        self._next_booking_id += 1
        # Store the booking.
        self._bookings[booking.booking_id] = booking
        # Return the new booking to the caller.
        return booking

    # Returns a booking by id; rejects unknown ids.
    def get_booking(self, booking_id):
        # Look up the booking.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            # Message describing the rejection.
            message = f"unknown booking {booking_id}"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Return the booking.
        return booking

    # Cancels an active booking and refunds its full price; the booking stays active if the refund fails.
    def cancel_booking(self, booking_id):
        # Look up the booking to cancel.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            # Message describing the rejection.
            message = f"unknown booking {booking_id}"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Reject bookings that were already cancelled.
        if booking.status is BookingStatus.CANCELLED:
            # Message describing the rejection.
            message = f"booking {booking_id} already cancelled"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Find the screening to read its start time and price.
        screening = self._screenings[booking.screening_id]
        # Read the current time from the clock.
        now = self._clock()
        # Reject cancellations made inside the cut-off window before the start.
        if now > screening.start_time - self.CANCELLATION_CUTOFF:
            # Message describing the rejection.
            message = f"booking {booking_id} is inside the cancellation cut-off"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Count the retries performed so far.
        retries = 0
        # Attempt the refund until it is accepted or the attempt is abandoned.
        while True:
            # Try one refund attempt against the gateway.
            try:
                # Ask the gateway to refund the full price.
                self._gateway.refund(booking_id, screening.price_cents)
                # Leave the loop once the gateway accepted the refund.
                break
            # Handle a transient gateway failure.
            except GatewayTransientError as error:
                # Log the transient failure with its cause.
                self._logger.warning("transient refund failure for booking %s: %s", booking_id, error)
                # Give up once the retry budget is spent.
                if retries >= self.MAX_REFUND_RETRIES:
                    # Record the failed refund on the booking.
                    booking.refund_status = RefundStatus.FAILED
                    # Message describing the rejection without gateway details.
                    message = f"refund for booking {booking_id} failed after retries"
                    # Log the rejection before raising it.
                    self._logger.error(message)
                    # Raise the generic service exception without chaining the cause.
                    raise ProcessingException(message) from None
                # Count this retry.
                retries += 1
            # Handle a permanent refusal from the gateway.
            except GatewayPermanentError as error:
                # Log the permanent failure with its cause.
                self._logger.error("permanent refund failure for booking %s: %s", booking_id, error)
                # Record the failed refund; the booking stays active.
                booking.refund_status = RefundStatus.FAILED
                # Message describing the rejection without gateway details.
                message = f"refund for booking {booking_id} was refused"
                # Raise the generic service exception without chaining the cause.
                raise ProcessingException(message) from None
            # Handle a gateway that cannot be reached.
            except GatewayUnavailableError as error:
                # Log the unavailability with its cause.
                self._logger.error("refund gateway unavailable for booking %s: %s", booking_id, error)
                # Reject the cancellation; the booking is left unchanged.
                raise ProcessingException(f"refund gateway unavailable for booking {booking_id}") from None
        # Mark the booking as cancelled now that the refund was accepted.
        booking.status = BookingStatus.CANCELLED
        # Record the accepted refund.
        booking.refund_status = RefundStatus.REFUNDED

    # Reports the refund status of a booking; rejects unknown ids.
    def get_refund_status(self, booking_id):
        # Look up the booking.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            # Message describing the rejection.
            message = f"unknown booking {booking_id}"
            # Log the rejection before raising it.
            self._logger.warning(message)
            # Raise the generic service exception.
            raise ProcessingException(message)
        # Return the refund status of the booking.
        return booking.refund_status
