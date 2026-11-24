# Module docstring stating what this module does
"""Seat booking for cinema screenings, with cancellation and refunds."""

# Import the logging module used to record every exception passing through the service
import logging
# Import the dataclass decorator used to declare plain data entities
from dataclasses import dataclass
# Import datetime for screening start times and timedelta for the cancellation deadline
from datetime import datetime, timedelta

# Create the module logger that records every exception passing through the service
LOGGER = logging.getLogger(__name__)

# Booking status meaning the seat is still held
BOOKING_ACTIVE = "active"
# Booking status meaning the seat was released by a cancellation
BOOKING_CANCELLED = "cancelled"
# Refund status meaning no refund has been attempted yet
REFUND_NOT_REQUESTED = "not_requested"
# Refund status meaning the payment gateway accepted the refund
REFUND_REFUNDED = "refunded"
# Refund status meaning the refund failed permanently or ran out of retries
REFUND_FAILED = "failed"


# Business rule violation raised for invalid seats, unknown bookings and late cancellations
class BookingRejectedError(Exception):
    # Carries only the reason message, no extra state
    pass


# Raised by the payment gateway when a refund failed but may succeed if retried
class PaymentGatewayTransientError(Exception):
    # Carries only the failure message, no extra state
    pass


# Raised by the payment gateway when a refund is refused and must not be retried
class PaymentGatewayPermanentError(Exception):
    # Carries only the failure message, no extra state
    pass


# Raised by the payment gateway when it cannot process refunds at the moment
class PaymentGatewayUnavailableError(Exception):
    # Carries only the failure message, no extra state
    pass


# Generic error raised at the service boundary so gateway details do not leak to callers
class ProcessingException(Exception):
    # Carries only the message, no extra state
    pass


# Plain data describing the seat layout of a room
@dataclass
class RoomEntity:
    # Number of rows in the room, numbered from 1
    rows: int
    # Number of seats in each row, numbered from 1
    seats_per_row: int


# Plain data describing one showing of a film in a room
@dataclass
class ScreeningEntity:
    # Identifier of the screening, used to match bookings to it
    screening_id: str
    # Moment the screening starts, used for the cancellation deadline
    start_time: datetime
    # Room in which the screening takes place
    room: RoomEntity
    # Ticket price in integer cents to avoid floating-point rounding
    price_cents: int


# Plain data describing one seat held by a client for a screening
@dataclass
class BookingEntity:
    # Identifier assigned when the booking is created
    booking_id: str
    # Screening the seat was booked for
    screening: ScreeningEntity
    # Row of the booked seat
    row: int
    # Seat number within the row
    seat: int
    # Client who holds the booking
    client_id: str
    # Whether the seat is still held (active) or released (cancelled)
    status: str = BOOKING_ACTIVE
    # Outcome of the refund attempted on cancellation
    refund_status: str = REFUND_NOT_REQUESTED


# Service holding all booking rules; the only class in this module with behavior
class BookingManager:
    # Number of retries after the first refund attempt fails transiently
    MAX_REFUND_RETRIES = 3
    # Cancellation is allowed only up to this long before the screening starts
    CANCELLATION_DEADLINE = timedelta(hours=2)

    # Store the payment gateway used for refunds and start with no bookings
    def __init__(self, payment_gateway):
        # Keep the payment gateway injected by the caller
        self._payment_gateway = payment_gateway
        # Keep every booking ever made, keyed by booking id
        self._bookings = {}

    # Book one seat on a screening for a client, rejecting seats outside the room or already held
    def book_seat(self, screening, row, seat, client_id):
        # Wrap the booking so every exception leaving this layer is logged before rethrow
        try:
            # Reject a seat position outside the room layout
            if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                # Raise the rejection for a seat that does not exist in the room
                raise BookingRejectedError("seat outside room layout")
            # Check whether an active booking already holds this seat on this screening
            taken = any(b.status == BOOKING_ACTIVE and b.screening.screening_id == screening.screening_id and b.row == row and b.seat == seat for b in self._bookings.values())
            # Reject the booking when the seat is already held
            if taken:
                # Raise the rejection for a seat already booked
                raise BookingRejectedError("seat already booked")
            # Build the booking id from the number of bookings made so far
            booking_id = str(len(self._bookings) + 1)
            # Create the booking as active with no refund requested yet
            booking = BookingEntity(booking_id=booking_id, screening=screening, row=row, seat=seat, client_id=client_id)
            # Store the booking so later cancellations and lookups can find it
            self._bookings[booking_id] = booking
            # Return the new booking to the caller
            return booking
        # Catch any exception leaving the booking so it is logged
        except Exception:
            # Log the exception with its traceback
            LOGGER.exception("book_seat failed for screening %s", screening.screening_id)
            # Rethrow the same exception to the caller
            raise

    # Cancel an active booking up to the deadline, refunding it through the payment gateway
    def cancel_booking(self, booking_id, now):
        # Wrap the cancellation so every exception leaving this layer is logged before rethrow
        try:
            # Look up the booking by id, getting None when it does not exist
            booking = self._bookings.get(booking_id)
            # Reject cancellation of a booking that was never made
            if booking is None:
                # Raise the rejection for an unknown booking
                raise BookingRejectedError("unknown booking")
            # Reject cancellation of a booking that is already released
            if booking.status != BOOKING_ACTIVE:
                # Raise the rejection for a repeated cancellation
                raise BookingRejectedError("booking already cancelled")
            # Reject cancellation made later than the deadline before the screening starts
            if now > booking.screening.start_time - self.CANCELLATION_DEADLINE:
                # Raise the rejection for a late cancellation
                raise BookingRejectedError("cancellation window closed")
            # Attempt the refund once, then retry up to MAX_REFUND_RETRIES times on transient failures
            for attempt in range(self.MAX_REFUND_RETRIES + 1):
                # Guard the gateway call so each failure kind can be handled separately
                try:
                    # Ask the gateway to refund the screening price for this booking
                    self._payment_gateway.refund(booking.booking_id, booking.screening.price_cents)
                    # Release the seat now that the refund went through
                    booking.status = BOOKING_CANCELLED
                    # Record that the refund succeeded
                    booking.refund_status = REFUND_REFUNDED
                    # Return the cancelled booking to the caller
                    return booking
                # Handle a transient gateway failure by trying the refund again
                except PaymentGatewayTransientError:
                    # Log the failed attempt with its traceback before retrying
                    LOGGER.warning("refund attempt %s for booking %s failed transiently", attempt + 1, booking_id, exc_info=True)
                # Handle a permanent refusal by keeping the booking active
                except PaymentGatewayPermanentError:
                    # Log the refusal with its traceback
                    LOGGER.warning("refund for booking %s refused permanently", booking_id, exc_info=True)
                    # Record that the refund failed
                    booking.refund_status = REFUND_FAILED
                    # Return the still-active booking to the caller
                    return booking
                # Handle an unavailable gateway by rejecting the cancellation
                except PaymentGatewayUnavailableError:
                    # Raise a generic processing error so gateway details do not leak
                    raise ProcessingException("cancellation rejected: payment gateway unavailable")
                # Handle any other gateway failure as an unexpected processing error
                except Exception:
                    # Raise a generic processing error for the unexpected gateway failure
                    raise ProcessingException("cancellation failed: unexpected payment gateway error")
            # Log that every attempt failed transiently and the refund did not go through
            LOGGER.warning("refund for booking %s failed after all retries", booking_id)
            # Record that the refund failed
            booking.refund_status = REFUND_FAILED
            # Return the still-active booking to the caller
            return booking
        # Catch any exception leaving the cancellation so it is logged
        except Exception:
            # Log the exception with its traceback
            LOGGER.exception("cancel_booking failed for booking %s", booking_id)
            # Rethrow the same exception to the caller
            raise

    # Report the refund status of a booking, rejecting unknown booking ids
    def get_refund_status(self, booking_id):
        # Wrap the lookup so every exception leaving this layer is logged before rethrow
        try:
            # Look up the booking by id, getting None when it does not exist
            booking = self._bookings.get(booking_id)
            # Reject a lookup for a booking that was never made
            if booking is None:
                # Raise the rejection for an unknown booking
                raise BookingRejectedError("unknown booking")
            # Return the refund status recorded on the booking
            return booking.refund_status
        # Catch any exception leaving the lookup so it is logged
        except Exception:
            # Log the exception with its traceback
            LOGGER.exception("get_refund_status failed for booking %s", booking_id)
            # Rethrow the same exception to the caller
            raise
