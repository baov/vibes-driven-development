"""Seat booking for cinema screenings, with cancellation and refund."""

# Logging is used to record every exception at the layer it passes through.
import logging
# Lock guards booking state against concurrent check-then-act races.
import threading
# Unique identifiers for bookings.
import uuid
# Dataclasses give plain, readable records for screenings and bookings.
from dataclasses import dataclass
# Time arithmetic for the cancellation deadline.
from datetime import datetime, timedelta

# Module logger, named after the package.
logger = logging.getLogger(__name__)

# Booking is active: the seat is held for the client.
BOOKING_ACTIVE = "ACTIVE"
# Booking is cancelled and refunded: the seat is free again.
BOOKING_CANCELLED = "CANCELLED"

# No refund has been requested for the booking.
REFUND_NOT_REQUESTED = "NOT_REQUESTED"
# A refund call to the gateway is in progress.
REFUND_PENDING = "PENDING"
# The gateway confirmed the refund.
REFUND_SUCCEEDED = "SUCCEEDED"
# The gateway refused the refund, or transient failures exhausted the retries.
REFUND_FAILED = "FAILED"

# Cancellation is allowed up to this long before the screening starts.
CANCELLATION_CUTOFF = timedelta(hours=2)
# Number of retries after a first transient failure (so up to 4 calls in total).
MAX_REFUND_RETRIES = 3


class ProcessingException(Exception):
    """Base error raised by the booking layer."""


class SeatUnavailableException(ProcessingException):
    """The seat is already booked, or does not exist in the room."""


class UnknownScreeningException(ProcessingException):
    """No screening is registered under the given identifier."""


class UnknownBookingException(ProcessingException):
    """No booking is registered under the given identifier."""


class BookingNotCancellableException(ProcessingException):
    """The booking is already cancelled, being cancelled, or past the deadline."""


class RefundFailedException(ProcessingException):
    """The refund was refused or kept failing; the booking stays active."""


class RefundUnavailableException(ProcessingException):
    """The payment gateway is unavailable; the cancellation is rejected."""


class TransientGatewayError(Exception):
    """Raised by a gateway for a failure that may succeed if retried."""


class PermanentGatewayError(Exception):
    """Raised by a gateway when the refund is definitively refused."""


class GatewayUnavailableError(Exception):
    """Raised by a gateway when it cannot be reached at all."""


@dataclass(frozen=True)
class Screening:
    """A screening: start time, room layout and seat price."""

    # Identifier of the screening.
    screening_id: str
    # Start time; compared with the injected clock, so use the same timezone convention.
    starts_at: datetime
    # Number of rows in the room, numbered 1..rows.
    rows: int
    # Number of seats in each row, numbered 1..seats_per_row.
    seats_per_row: int
    # Price of one seat, passed unchanged to the gateway on refund.
    price: object


@dataclass
class Booking:
    """A client's booking of one seat for one screening."""

    # Identifier of the booking; also used as the refund idempotency key.
    booking_id: str
    # Screening the seat is booked for.
    screening_id: str
    # Client who booked the seat.
    client_id: str
    # Row of the seat.
    row: int
    # Seat number in the row.
    seat: int
    # Price paid, refunded in full on cancellation.
    price: object
    # Either BOOKING_ACTIVE or BOOKING_CANCELLED.
    status: str = BOOKING_ACTIVE
    # One of the REFUND_* values.
    refund_status: str = REFUND_NOT_REQUESTED


class BookingManager:
    """Books seats, cancels bookings and refunds them through a payment gateway.

    The gateway must expose ``refund(booking_id, amount)`` and signal failures by
    raising TransientGatewayError, PermanentGatewayError or GatewayUnavailableError.
    """

    def __init__(self, payment_gateway, clock=datetime.now):
        # Gateway used for refunds.
        self._payment_gateway = payment_gateway
        # Callable returning the current time; injectable for tests.
        self._clock = clock
        # Screenings by identifier.
        self._screenings = {}
        # Bookings by identifier.
        self._bookings = {}
        # Active booking identifier by (screening_id, row, seat).
        self._booked_seats = {}
        # Serializes every read-modify-write of the dictionaries above.
        self._lock = threading.Lock()

    def add_screening(self, screening):
        # Register (or replace) the screening under its identifier.
        with self._lock:
            # Store the screening.
            self._screenings[screening.screening_id] = screening

    def book_seat(self, screening_id, client_id, row, seat):
        # Check-and-reserve must be atomic, otherwise two clients could get the same seat.
        with self._lock:
            # Look up the screening.
            screening = self._screenings.get(screening_id)
            # An unknown screening cannot be booked.
            if screening is None:
                # Build the error before logging it.
                error = UnknownScreeningException(f"Unknown screening {screening_id}")
                # Log at this layer, then raise.
                logger.warning("Booking rejected: %s", error)
                # Reject the booking.
                raise error
            # The seat must exist in the room.
            if not (1 <= row <= screening.rows and 1 <= seat <= screening.seats_per_row):
                # Build the error before logging it.
                error = SeatUnavailableException(f"Seat {row}-{seat} does not exist in screening {screening_id}")
                # Log at this layer, then raise.
                logger.warning("Booking rejected: %s", error)
                # Reject the booking.
                raise error
            # Key identifying the physical seat for this screening.
            seat_key = (screening_id, row, seat)
            # A seat held by an active booking cannot be booked again.
            if seat_key in self._booked_seats:
                # Build the error before logging it.
                error = SeatUnavailableException(f"Seat {row}-{seat} is already booked for screening {screening_id}")
                # Log at this layer, then raise.
                logger.warning("Booking rejected: %s", error)
                # Reject the booking.
                raise error
            # Create the booking at the screening's current price.
            booking = Booking(
                booking_id=str(uuid.uuid4()),
                screening_id=screening_id,
                client_id=client_id,
                row=row,
                seat=seat,
                price=screening.price,
            )
            # Record the booking.
            self._bookings[booking.booking_id] = booking
            # Mark the seat as taken.
            self._booked_seats[seat_key] = booking.booking_id
            # Hand the booking back to the caller.
            return booking

    def cancel_booking(self, booking_id):
        # Phase 1, under the lock: validate and mark the refund as pending so a
        # concurrent cancellation of the same booking is rejected.
        with self._lock:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # An unknown booking cannot be cancelled.
            if booking is None:
                # Build the error before logging it.
                error = UnknownBookingException(f"Unknown booking {booking_id}")
                # Log at this layer, then raise.
                logger.warning("Cancellation rejected: %s", error)
                # Reject the cancellation.
                raise error
            # A cancelled booking, or one whose refund is in flight, cannot be cancelled again.
            if booking.status == BOOKING_CANCELLED or booking.refund_status == REFUND_PENDING:
                # Build the error before logging it.
                error = BookingNotCancellableException(f"Booking {booking_id} is already cancelled")
                # Log at this layer, then raise.
                logger.warning("Cancellation rejected: %s", error)
                # Reject the cancellation.
                raise error
            # Screening of the booking, needed for the deadline.
            screening = self._screenings[booking.screening_id]
            # Cancelling exactly two hours before the start is still allowed.
            if self._clock() > screening.starts_at - CANCELLATION_CUTOFF:
                # Build the error before logging it.
                error = BookingNotCancellableException(
                    f"Booking {booking_id} can no longer be cancelled: less than two hours before the screening"
                )
                # Log at this layer, then raise.
                logger.warning("Cancellation rejected: %s", error)
                # Reject the cancellation.
                raise error
            # Remember the refund status to restore if the gateway is unavailable.
            previous_refund_status = booking.refund_status
            # Claim the booking for this cancellation.
            booking.refund_status = REFUND_PENDING

        # Phase 2, outside the lock: call the gateway, which may be slow.
        try:
            # Request the refund, retrying transient failures.
            self._refund_with_retries(booking)
        except GatewayUnavailableError as exc:
            # Nothing was attempted: restore the previous refund status.
            with self._lock:
                # Restore the status.
                booking.refund_status = previous_refund_status
            # Log at this layer before wrapping.
            logger.error("Cancellation of booking %s rejected: payment gateway unavailable", booking_id)
            # Wrap at the layer boundary; keep the cause for debugging.
            raise RefundUnavailableException(f"Payment gateway unavailable, booking {booking_id} not cancelled") from exc
        except (PermanentGatewayError, TransientGatewayError) as exc:
            # The refund failed: the booking stays active.
            with self._lock:
                # Record the failure.
                booking.refund_status = REFUND_FAILED
            # Log at this layer before wrapping.
            logger.error("Refund of booking %s failed, booking stays active: %r", booking_id, exc)
            # Wrap at the layer boundary; keep the cause for debugging.
            raise RefundFailedException(f"Refund failed, booking {booking_id} stays active") from exc

        # Phase 3, under the lock: the refund went through, release the seat.
        with self._lock:
            # Mark the refund as done.
            booking.refund_status = REFUND_SUCCEEDED
            # Mark the booking as cancelled.
            booking.status = BOOKING_CANCELLED
            # Free the seat for other clients.
            del self._booked_seats[(booking.screening_id, booking.row, booking.seat)]
        # Hand the updated booking back to the caller.
        return booking

    def _refund_with_retries(self, booking):
        # One initial attempt plus MAX_REFUND_RETRIES retries.
        for attempt in range(1 + MAX_REFUND_RETRIES):
            try:
                # The booking id lets the gateway deduplicate retried refunds.
                self._payment_gateway.refund(booking.booking_id, booking.price)
                # Success: stop retrying.
                return
            except TransientGatewayError:
                # Log every transient failure.
                logger.warning("Transient refund failure for booking %s (attempt %d)", booking.booking_id, attempt + 1)
                # Out of retries: propagate the last failure.
                if attempt == MAX_REFUND_RETRIES:
                    # Rethrow to the caller.
                    raise

    def get_refund_status(self, booking_id):
        # Read under the lock for a consistent view.
        with self._lock:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # An unknown booking has no refund status.
            if booking is None:
                # Build the error before logging it.
                error = UnknownBookingException(f"Unknown booking {booking_id}")
                # Log at this layer, then raise.
                logger.warning("Refund status lookup failed: %s", error)
                # Reject the lookup.
                raise error
            # Return one of the REFUND_* values.
            return booking.refund_status
