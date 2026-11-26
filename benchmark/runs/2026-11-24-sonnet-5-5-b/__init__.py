# Seat booking with cancellation and refund (single module, see AGENTS.md: locality of behavior).
# Standard logging module used to log every exception at every layer.
import logging
# Date and time types for screening start and cancellation window.
from datetime import datetime, timedelta
# Counter used to generate booking identifiers.
import itertools

# Module logger.
logger = logging.getLogger(__name__)

# Refund statuses exposed for a booking.
REFUND_NONE = "NONE"
# Refund went through.
REFUND_REFUNDED = "REFUNDED"
# Refund failed definitively; the booking stays active.
REFUND_FAILED = "FAILED"

# Number of retries after the first attempt on a transient gateway failure.
MAX_REFUND_RETRIES = 3
# Cancellation is allowed until this long before the screening starts.
CANCELLATION_WINDOW = timedelta(hours=2)


# Generic exception raised at the service boundary; the original cause is deliberately omitted.
class ProcessingException(Exception):
    # Build the exception with a message and a machine-readable reason.
    def __init__(self, message, reason):
        # Initialise the base exception with the message.
        super().__init__(message)
        # Keep the reason so callers can tell rejections apart.
        self.reason = reason


# Gateway failure that may succeed when retried.
class TransientGatewayError(Exception):
    pass


# Gateway failure that will never succeed.
class PermanentGatewayError(Exception):
    pass


# Gateway cannot be reached at all.
class GatewayUnavailableError(Exception):
    pass


# A room is a grid of rows and seats per row.
class Room:
    # Store the dimensions.
    def __init__(self, rows, seats_per_row):
        # Number of rows.
        self.rows = rows
        # Number of seats in each row.
        self.seats_per_row = seats_per_row

    # Tell whether a (row, seat) pair exists in the room (1-based).
    def has_seat(self, row, seat):
        # Both coordinates must be within bounds.
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


# A screening has an id, a start time, a room and a price.
class Screening:
    # Store the screening attributes.
    def __init__(self, screening_id, start_time, room, price):
        # Identifier of the screening.
        self.screening_id = screening_id
        # Start datetime.
        self.start_time = start_time
        # Room where it takes place.
        self.room = room
        # Price of one seat.
        self.price = price


# A booking of one seat by one client for one screening.
class Booking:
    # Store the booking attributes.
    def __init__(self, booking_id, client_id, screening, row, seat):
        # Identifier of the booking.
        self.booking_id = booking_id
        # Client who booked.
        self.client_id = client_id
        # Booked screening.
        self.screening = screening
        # Booked row.
        self.row = row
        # Booked seat.
        self.seat = seat
        # Active until cancelled.
        self.cancelled = False
        # Refund status, none until a refund is attempted.
        self.refund_status = REFUND_NONE


# Service handling bookings, cancellations and refunds.
class BookingManager:
    # The gateway is passed in; the clock is injectable for tests.
    def __init__(self, gateway, clock=datetime.now):
        # Payment gateway used for refunds.
        self.gateway = gateway
        # Callable returning the current datetime.
        self.clock = clock
        # Bookings by id.
        self.bookings = {}
        # Booking id generator.
        self.counter = itertools.count(1)

    # Reject a request: log it, then raise the generic exception.
    def reject(self, message, reason):
        # Log the rejection.
        logger.warning("Rejected: %s (%s)", message, reason)
        # Raise the generic exception.
        raise ProcessingException(message, reason)

    # Book a seat; returns the new Booking.
    def book(self, client_id, screening, row, seat):
        # The seat must exist in the room.
        if not screening.room.has_seat(row, seat):
            # Reject unknown seats.
            self.reject("Seat does not exist", "invalid_seat")
        # Booking after the start is not possible.
        if self.clock() >= screening.start_time:
            # Reject started screenings.
            self.reject("Screening already started", "screening_started")
        # Look through existing bookings.
        for info in self.bookings.values():
            # An active booking on the same screening and seat blocks the new one.
            if (not info.cancelled and info.screening.screening_id == screening.screening_id
                    and info.row == row and info.seat == seat):
                # Reject double booking.
                self.reject("Seat already booked", "seat_taken")
        # Create the booking with a new id.
        booking = Booking(next(self.counter), client_id, screening, row, seat)
        # Store it.
        self.bookings[booking.booking_id] = booking
        # Return it.
        return booking

    # Cancel a booking and refund it through the gateway.
    def cancel(self, booking_id):
        # Find the booking.
        booking = self.bookings.get(booking_id)
        # Unknown booking.
        if booking is None:
            # Reject it.
            self.reject("Unknown booking", "unknown_booking")
        # Already cancelled booking.
        if booking.cancelled:
            # Reject it.
            self.reject("Booking already cancelled", "already_cancelled")
        # Cancellation closes two hours before the start.
        if self.clock() > booking.screening.start_time - CANCELLATION_WINDOW:
            # Reject late cancellations.
            self.reject("Too late to cancel", "too_late")
        # One initial attempt plus the retries.
        for attempt in range(MAX_REFUND_RETRIES + 1):
            # Try the refund.
            try:
                # Refund the screening price.
                self.gateway.refund(booking.booking_id, booking.screening.price)
            # Transient failure: retry unless attempts are exhausted.
            except TransientGatewayError:
                # Log the failure.
                logger.exception("Transient refund failure (attempt %s)", attempt + 1)
                # Retry while attempts remain.
                if attempt < MAX_REFUND_RETRIES:
                    # Next attempt.
                    continue
                # Retries exhausted: treat as a permanent failure.
                booking.refund_status = REFUND_FAILED
                # Wrap and rethrow without the cause.
                raise ProcessingException("Refund failed", "refund_failed") from None
            # Permanent failure: the booking stays active.
            except PermanentGatewayError:
                # Log the failure.
                logger.exception("Permanent refund failure")
                # Record the failure.
                booking.refund_status = REFUND_FAILED
                # Wrap and rethrow without the cause.
                raise ProcessingException("Refund failed", "refund_failed") from None
            # Gateway unavailable: the cancellation is rejected.
            except GatewayUnavailableError:
                # Log the failure.
                logger.exception("Payment gateway unavailable")
                # Wrap and rethrow without the cause.
                raise ProcessingException("Payment gateway unavailable", "gateway_unavailable") from None
            # Refund succeeded.
            else:
                # Mark refunded.
                booking.refund_status = REFUND_REFUNDED
                # Mark cancelled.
                booking.cancelled = True
                # Stop retrying.
                break
        # Return the cancelled booking.
        return booking

    # Expose the refund status of a booking.
    def get_refund_status(self, booking_id):
        # Find the booking.
        booking = self.bookings.get(booking_id)
        # Unknown booking.
        if booking is None:
            # Reject it.
            self.reject("Unknown booking", "unknown_booking")
        # Return its status.
        return booking.refund_status
