"""Seat booking with cancellation and refund (single module, see AGENTS.md section 1)."""
# Import the logging module used to log every exception at every layer.
import logging
# Import the dataclass decorator: entities are plain data (pragmatic-domain-design).
from dataclasses import dataclass
# Import datetime and timedelta for screening times and the cancellation cutoff.
from datetime import datetime, timedelta

# Module logger used by every layer of this module.
LOGGER = logging.getLogger(__name__)

# Booking status: the seat is held by the client.
STATUS_ACTIVE = "active"
# Booking status: the booking was cancelled and refunded.
STATUS_CANCELLED = "cancelled"

# Refund status: no refund attempted yet.
REFUND_NONE = "none"
# Refund status: the gateway refunded the booking.
REFUND_REFUNDED = "refunded"
# Refund status: the gateway failed permanently (or transient failures exhausted the retries).
REFUND_FAILED = "failed"
# Refund status: the gateway was unavailable.
REFUND_UNAVAILABLE = "unavailable"

# Rejection reason: the seat is already booked for this screening.
REASON_SEAT_TAKEN = "seat_already_booked"
# Rejection reason: the seat does not exist in the room.
REASON_UNKNOWN_SEAT = "unknown_seat"
# Rejection reason: the screening does not exist.
REASON_UNKNOWN_SCREENING = "unknown_screening"
# Rejection reason: the screening already started.
REASON_SCREENING_STARTED = "screening_started"
# Rejection reason: the booking does not exist.
REASON_UNKNOWN_BOOKING = "unknown_booking"
# Rejection reason: the booking is already cancelled.
REASON_ALREADY_CANCELLED = "already_cancelled"
# Rejection reason: less than two hours before the screening.
REASON_TOO_LATE = "too_late_to_cancel"
# Rejection reason: the gateway failed permanently, the booking stays active.
REASON_REFUND_FAILED = "refund_failed"
# Rejection reason: the gateway is unavailable, the cancellation is rejected.
REASON_GATEWAY_UNAVAILABLE = "gateway_unavailable"

# Number of retries after the first attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3
# Cancellation is allowed up to this long before the screening starts.
CANCELLATION_CUTOFF = timedelta(hours=2)


# Generic exception exposed at the layer boundary (original cause intentionally omitted).
class ProcessingException(Exception):
    """Generic exception for unexpected failures."""


# Business rejection raised by BookingManager, carrying a machine readable reason.
class BookingRejectedException(ProcessingException):
    """A booking or cancellation request was rejected."""

    # Store the reason alongside the message.
    def __init__(self, reason):
        # Initialise the base exception with the reason as message.
        super().__init__(reason)
        # Keep the reason for callers.
        self.reason = reason


# Raised by a gateway when a refund failed but may succeed on retry.
class TransientGatewayException(Exception):
    """Transient gateway failure."""


# Raised by a gateway when a refund failed and will never succeed.
class PermanentGatewayException(Exception):
    """Permanent gateway failure."""


# Raised by a gateway when it cannot be reached at all.
class GatewayUnavailableException(Exception):
    """Gateway unavailable."""


# Contract of the payment gateway passed to BookingManager.
class PaymentGatewayHandler:
    """Payment gateway: refund(booking_id, amount_cents) or raise one of the gateway exceptions."""

    # Refund the amount (in cents) for the booking.
    def refund(self, booking_id, amount_cents):
        # Concrete gateways override this method.
        raise NotImplementedError


# A screening: start time, room dimensions and price (in cents).
@dataclass
class Screening:
    # Identifier of the screening.
    id: str
    # Start time of the screening.
    start_time: datetime
    # Number of rows in the room.
    rows: int
    # Number of seats in each row.
    seats_per_row: int
    # Ticket price in cents.
    price_cents: int


# A booking of one seat for one screening by one client.
@dataclass
class Booking:
    # Identifier of the booking.
    id: str
    # Identifier of the screening.
    screening_id: str
    # Identifier of the client.
    client_id: str
    # Row of the seat (1-based).
    row: int
    # Seat number in the row (1-based).
    seat: int
    # Booking status, see STATUS_* constants.
    status: str = STATUS_ACTIVE
    # Refund status, see REFUND_* constants.
    refund_status: str = REFUND_NONE


# Service booking seats, cancelling bookings and refunding through the gateway.
class BookingManager:
    """Books seats, cancels bookings and exposes their refund status."""

    # Build the manager with the payment gateway and an optional clock (for tests).
    def __init__(self, gateway, clock=None):
        # Keep the gateway used for refunds.
        self._gateway = gateway
        # Keep the clock, defaulting to the system time.
        self._clock = clock if clock is not None else datetime.now
        # Screenings by identifier.
        self._screenings = {}
        # Bookings by identifier.
        self._bookings = {}
        # Counter used to generate booking identifiers.
        self._next_id = 1

    # Register a screening so seats can be booked for it.
    def add_screening(self, screening):
        # Store the screening by its identifier.
        self._screenings[screening.id] = screening
        # Return the screening for convenience.
        return screening

    # Book a seat for a client; reject a seat that is already booked.
    def book_seat(self, client_id, screening_id, row, seat):
        # Run the whole operation so every exception is logged then rethrown.
        try:
            # Look up the screening.
            info = self._screenings.get(screening_id)
            # Reject an unknown screening.
            if info is None:
                # Raise the rejection.
                raise BookingRejectedException(REASON_UNKNOWN_SCREENING)
            # Reject bookings once the screening has started.
            if self._clock() >= info.start_time:
                # Raise the rejection.
                raise BookingRejectedException(REASON_SCREENING_STARTED)
            # Reject a seat outside the room.
            if not (1 <= row <= info.rows and 1 <= seat <= info.seats_per_row):
                # Raise the rejection.
                raise BookingRejectedException(REASON_UNKNOWN_SEAT)
            # Check every existing booking for the same seat.
            for existing in self._bookings.values():
                # An active booking of the same seat of the same screening blocks the request.
                if (existing.status == STATUS_ACTIVE and existing.screening_id == screening_id
                        and existing.row == row and existing.seat == seat):
                    # Raise the rejection.
                    raise BookingRejectedException(REASON_SEAT_TAKEN)
            # Create the booking.
            result = Booking(id="B%d" % self._next_id, screening_id=screening_id,
                             client_id=client_id, row=row, seat=seat)
            # Advance the identifier counter.
            self._next_id += 1
            # Store the booking.
            self._bookings[result.id] = result
            # Return the booking.
            return result
        # Business rejections keep their type.
        except BookingRejectedException as error:
            # Log the exception.
            LOGGER.exception("book_seat rejected: %s", error)
            # Rethrow it.
            raise
        # Any other failure is wrapped in the generic exception.
        except Exception:
            # Log the exception.
            LOGGER.exception("book_seat failed")
            # Rethrow a generic exception without the original cause.
            raise ProcessingException("book_seat failed") from None

    # Cancel a booking up to two hours before the screening and refund it.
    def cancel_booking(self, booking_id):
        # Run the whole operation so every exception is logged then rethrown.
        try:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # Reject an unknown booking.
            if booking is None:
                # Raise the rejection.
                raise BookingRejectedException(REASON_UNKNOWN_BOOKING)
            # Reject an already cancelled booking.
            if booking.status == STATUS_CANCELLED:
                # Raise the rejection.
                raise BookingRejectedException(REASON_ALREADY_CANCELLED)
            # Look up the screening of the booking.
            info = self._screenings[booking.screening_id]
            # Reject cancellations less than two hours before the start.
            if info.start_time - self._clock() < CANCELLATION_CUTOFF:
                # Raise the rejection.
                raise BookingRejectedException(REASON_TOO_LATE)
            # Count the gateway attempts.
            attempts = 0
            # Try the refund until it succeeds or fails for good.
            while True:
                # Count this attempt.
                attempts += 1
                # Call the gateway.
                try:
                    # Refund the ticket price.
                    self._gateway.refund(booking.id, info.price_cents)
                    # Record the successful refund.
                    booking.refund_status = REFUND_REFUNDED
                    # Leave the retry loop.
                    break
                # Transient failure: retry up to MAX_REFUND_RETRIES times.
                except TransientGatewayException:
                    # Log the exception.
                    LOGGER.exception("refund attempt %d failed transiently", attempts)
                    # Give up once the first attempt and every retry failed.
                    if attempts > MAX_REFUND_RETRIES:
                        # Record the failed refund, the booking stays active.
                        booking.refund_status = REFUND_FAILED
                        # Reject the cancellation.
                        raise BookingRejectedException(REASON_REFUND_FAILED) from None
                # Permanent failure: no retry.
                except PermanentGatewayException:
                    # Log the exception.
                    LOGGER.exception("refund failed permanently")
                    # Record the failed refund, the booking stays active.
                    booking.refund_status = REFUND_FAILED
                    # Reject the cancellation.
                    raise BookingRejectedException(REASON_REFUND_FAILED) from None
                # Gateway unavailable: the cancellation is rejected.
                except GatewayUnavailableException:
                    # Log the exception.
                    LOGGER.exception("gateway unavailable")
                    # Record the unavailable gateway, the booking stays active.
                    booking.refund_status = REFUND_UNAVAILABLE
                    # Reject the cancellation.
                    raise BookingRejectedException(REASON_GATEWAY_UNAVAILABLE) from None
            # The refund went through: cancel the booking.
            booking.status = STATUS_CANCELLED
            # Return the cancelled booking.
            return booking
        # Business rejections keep their type.
        except BookingRejectedException as error:
            # Log the exception.
            LOGGER.exception("cancel_booking rejected: %s", error)
            # Rethrow it.
            raise
        # Any other failure is wrapped in the generic exception.
        except Exception:
            # Log the exception.
            LOGGER.exception("cancel_booking failed")
            # Rethrow a generic exception without the original cause.
            raise ProcessingException("cancel_booking failed") from None

    # Expose the refund status of a booking.
    def get_refund_status(self, booking_id):
        # Run the whole operation so every exception is logged then rethrown.
        try:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # Reject an unknown booking.
            if booking is None:
                # Raise the rejection.
                raise BookingRejectedException(REASON_UNKNOWN_BOOKING)
            # Return the refund status.
            return booking.refund_status
        # Business rejections keep their type.
        except BookingRejectedException as error:
            # Log the exception.
            LOGGER.exception("get_refund_status rejected: %s", error)
            # Rethrow it.
            raise
        # Any other failure is wrapped in the generic exception.
        except Exception:
            # Log the exception.
            LOGGER.exception("get_refund_status failed")
            # Rethrow a generic exception without the original cause.
            raise ProcessingException("get_refund_status failed") from None
