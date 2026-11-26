# Standard logging, used to log every exception at every layer.
import logging
# Date arithmetic for the cancellation deadline.
from datetime import datetime, timedelta

# Module logger.
logger = logging.getLogger(__name__)

# Cancellation is allowed up to this long before the screening starts.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Number of retries after the first refund attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3

# Booking lifecycle states.
BOOKING_ACTIVE = "ACTIVE"
BOOKING_CANCELLED = "CANCELLED"

# Refund states exposed to callers.
REFUND_NOT_REQUESTED = "NOT_REQUESTED"
REFUND_REFUNDED = "REFUNDED"
REFUND_FAILED = "FAILED"
REFUND_UNAVAILABLE = "UNAVAILABLE"


# Generic exception exposed at the service boundary; the original cause is omitted.
class ProcessingException(Exception):
    # Keep a short machine-readable reason next to the message.
    def __init__(self, message, reason="PROCESSING_ERROR"):
        # Initialise the base exception with the message.
        super().__init__(message)
        # Store the reason code.
        self.reason = reason


# Gateway failure that may succeed when retried.
class TransientGatewayError(Exception):
    pass


# Gateway failure that will never succeed (refund refused).
class PermanentGatewayError(Exception):
    pass


# Gateway cannot be reached at all.
class GatewayUnavailableError(Exception):
    pass


# Contract of the payment gateway passed to the service.
class PaymentGateway:
    # Refund an amount for a booking; raises one of the gateway errors on failure.
    def refund(self, booking_id, amount):
        # Real gateways override this method.
        raise NotImplementedError()


# Room layout: plain data.
class Room:
    # Store the layout.
    def __init__(self, rows, seats_per_row):
        # Number of rows.
        self.rows = rows
        # Number of seats in each row.
        self.seats_per_row = seats_per_row


# Screening: plain data.
class Screening:
    # Store the screening fields.
    def __init__(self, screening_id, start_time, room, price):
        # Identifier.
        self.screening_id = screening_id
        # Start time (datetime).
        self.start_time = start_time
        # Room where it takes place.
        self.room = room
        # Seat price.
        self.price = price


# Booking: plain data.
class Booking:
    # Store the booking fields.
    def __init__(self, booking_id, client_id, screening, row, seat):
        # Identifier.
        self.booking_id = booking_id
        # Client who booked.
        self.client_id = client_id
        # Booked screening.
        self.screening = screening
        # Booked row (1-based).
        self.row = row
        # Booked seat in the row (1-based).
        self.seat = seat
        # Lifecycle state.
        self.status = BOOKING_ACTIVE
        # Refund state.
        self.refund_status = REFUND_NOT_REQUESTED


# Service holding the booking, cancellation and refund rules.
class BookingService:
    # The gateway and the clock are passed in.
    def __init__(self, payment_gateway, clock=datetime.now):
        # Gateway used for refunds.
        self.payment_gateway = payment_gateway
        # Clock returning the current datetime.
        self.clock = clock
        # Bookings by identifier.
        self.bookings = {}
        # Sequence used to build identifiers.
        self.next_id = 1

    # Book a seat; rejects invalid seats, started screenings and already booked seats.
    def book_seat(self, client_id, screening, row, seat):
        # Layers log then rethrow every exception.
        try:
            # The screening must not have started.
            if self.clock() >= screening.start_time:
                # Reject.
                raise ProcessingException("Screening already started", "SCREENING_STARTED")
            # The seat must exist in the room.
            if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                # Reject.
                raise ProcessingException("Unknown seat", "UNKNOWN_SEAT")
            # Look for an active booking of the same seat.
            for existing in self.bookings.values():
                # Same screening, same seat, still active.
                if (existing.screening is screening and existing.row == row
                        and existing.seat == seat and existing.status == BOOKING_ACTIVE):
                    # Reject.
                    raise ProcessingException("Seat already booked", "SEAT_ALREADY_BOOKED")
            # Build the identifier.
            booking_id = "B%d" % self.next_id
            # Advance the sequence.
            self.next_id += 1
            # Create the booking.
            result = Booking(booking_id, client_id, screening, row, seat)
            # Store it.
            self.bookings[booking_id] = result
            # Return it.
            return result
        # Already a boundary exception.
        except ProcessingException as error:
            # Log it.
            logger.error("book_seat failed: %s", error)
            # Rethrow it.
            raise
        # Anything else is wrapped.
        except Exception as error:
            # Log it.
            logger.error("book_seat failed: %r", error)
            # Wrap without the cause.
            raise ProcessingException("Booking failed") from None

    # Cancel a booking at least two hours before the screening and refund it.
    def cancel_booking(self, booking_id):
        # Layers log then rethrow every exception.
        try:
            # Find the booking.
            booking = self.bookings.get(booking_id)
            # Unknown booking.
            if booking is None:
                # Reject.
                raise ProcessingException("Unknown booking", "UNKNOWN_BOOKING")
            # Already cancelled.
            if booking.status == BOOKING_CANCELLED:
                # Reject.
                raise ProcessingException("Booking already cancelled", "ALREADY_CANCELLED")
            # Too late to cancel.
            if booking.screening.start_time - self.clock() < CANCELLATION_DEADLINE:
                # Reject.
                raise ProcessingException("Too late to cancel", "TOO_LATE")
            # First attempt plus retries.
            for attempt in range(1 + MAX_REFUND_RETRIES):
                # Try the refund.
                try:
                    # Call the gateway.
                    self.payment_gateway.refund(booking.booking_id, booking.screening.price)
                    # Refund done.
                    booking.refund_status = REFUND_REFUNDED
                    # Cancel the booking.
                    booking.status = BOOKING_CANCELLED
                    # Done.
                    return booking
                # Transient failure: retry.
                except TransientGatewayError as error:
                    # Log it.
                    logger.warning("refund attempt %d failed: %r", attempt + 1, error)
                # Permanent failure: stop, booking stays active.
                except PermanentGatewayError as error:
                    # Log it.
                    logger.error("refund refused: %r", error)
                    # Remember the failure.
                    booking.refund_status = REFUND_FAILED
                    # Reject.
                    raise ProcessingException("Refund refused", "REFUND_FAILED") from None
                # Gateway down: reject the cancellation.
                except GatewayUnavailableError as error:
                    # Log it.
                    logger.error("gateway unavailable: %r", error)
                    # Remember the failure.
                    booking.refund_status = REFUND_UNAVAILABLE
                    # Reject.
                    raise ProcessingException("Payment gateway unavailable", "GATEWAY_UNAVAILABLE") from None
            # Retries exhausted: treated like a refused refund, booking stays active.
            booking.refund_status = REFUND_FAILED
            # Reject.
            raise ProcessingException("Refund failed after retries", "REFUND_FAILED")
        # Already a boundary exception.
        except ProcessingException as error:
            # Log it.
            logger.error("cancel_booking failed: %s", error)
            # Rethrow it.
            raise
        # Anything else is wrapped.
        except Exception as error:
            # Log it.
            logger.error("cancel_booking failed: %r", error)
            # Wrap without the cause.
            raise ProcessingException("Cancellation failed") from None

    # Expose the refund status of a booking.
    def get_refund_status(self, booking_id):
        # Layers log then rethrow every exception.
        try:
            # Find the booking.
            booking = self.bookings.get(booking_id)
            # Unknown booking.
            if booking is None:
                # Reject.
                raise ProcessingException("Unknown booking", "UNKNOWN_BOOKING")
            # Return the status.
            return booking.refund_status
        # Already a boundary exception.
        except ProcessingException as error:
            # Log it.
            logger.error("get_refund_status failed: %s", error)
            # Rethrow it.
            raise
