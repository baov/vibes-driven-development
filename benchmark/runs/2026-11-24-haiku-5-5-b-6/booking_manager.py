# Seat booking, cancellation and refund for cinema screenings.
import itertools
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from seat_booking.payment_gateway import (
    PaymentGatewayUnavailableError,
    PermanentPaymentError,
    TransientPaymentError,
)

# Logger that records every rejection and gateway failure in this module.
logger = logging.getLogger(__name__)

# Cancellations are accepted up to this long before the screening starts.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Retries allowed after the first refund attempt when the gateway fails transiently.
MAX_TRANSIENT_RETRIES = 3

# Booking status: the seat is held for the client.
ACTIVE = "ACTIVE"
# Booking status: the client cancelled and the refund was accepted.
CANCELLED = "CANCELLED"

# Refund status: no refund has been requested or completed.
REFUND_NONE = "NONE"
# Refund status: the gateway accepted the refund.
REFUND_REFUNDED = "REFUNDED"
# Refund status: the gateway refused permanently or retries were exhausted.
REFUND_FAILED = "FAILED"


# Generic error for every rejected operation; gateway errors are wrapped in it at this layer.
class ProcessingException(Exception):
    pass


# Plain data describing a screening; behavior lives in BookingManager.
@dataclass
class Screening:
    # Unique identifier of the screening.
    screening_id: str
    # Start time of the screening; must be timezone-aware.
    start_time: datetime
    # Number of rows in the room; rows are numbered from 1.
    rows: int
    # Number of seats in each row; seats are numbered from 1.
    seats_per_row: int
    # Ticket price in integer cents, avoiding floating-point rounding on refunds.
    price_cents: int


# Plain data describing one seat held by a client for a screening.
@dataclass
class Booking:
    # Unique identifier of the booking.
    booking_id: str
    # Screening the seat belongs to.
    screening_id: str
    # Client who holds the seat.
    client_id: str
    # Row of the seat.
    row: int
    # Seat number within the row.
    seat: int
    # Either ACTIVE or CANCELLED.
    status: str = ACTIVE
    # Refund status of the booking, one of the REFUND_* values.
    refund_status: str = REFUND_NONE


# Books seats, cancels bookings and reports refund status.
class BookingManager:
    # Store the gateway and clock; the clock defaults to the current UTC time.
    def __init__(self, gateway, clock=None):
        # Keep the payment gateway used for refunds.
        self._gateway = gateway
        # Keep the clock used to decide whether a cancellation is still allowed.
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Screenings known to the manager, keyed by screening id.
        self._screenings = {}
        # Bookings issued so far, keyed by booking id.
        self._bookings = {}
        # Source of fresh booking ids.
        self._booking_ids = itertools.count(1)

    # Register a screening so seats can be booked for it.
    def add_screening(self, screening):
        # Store the screening under its id, replacing any previous entry.
        self._screenings[screening.screening_id] = screening

    # Reserve a seat for a client; rejects unknown screenings, seats outside the room and seats already held.
    def book_seat(self, screening_id, client_id, row, seat):
        # Check that the requested screening exists.
        if screening_id not in self._screenings:
            # Record the rejection before raising it.
            logger.warning("Booking rejected: unknown screening %s", screening_id)
            # Reject the booking because the screening does not exist.
            raise ProcessingException("Unknown screening")
        # Fetch the room layout of the screening.
        screening = self._screenings[screening_id]
        # Check that the seat coordinates lie inside the room.
        if not (1 <= row <= screening.rows and 1 <= seat <= screening.seats_per_row):
            # Record the rejection before raising it.
            logger.warning("Booking rejected: seat %s-%s outside room for screening %s", row, seat, screening_id)
            # Reject the booking because the seat does not exist in the room.
            raise ProcessingException("Seat outside the room")
        # Look through every existing booking for one that holds the same seat.
        for existing in self._bookings.values():
            # Compare the screening, seat and status of the existing booking with the request.
            if existing.screening_id == screening_id and existing.row == row and existing.seat == seat and existing.status == ACTIVE:
                # Record the rejection before raising it.
                logger.warning("Booking rejected: seat %s-%s already booked for screening %s", row, seat, screening_id)
                # Reject the booking because the seat is already held.
                raise ProcessingException("Seat already booked")
        # Create the booking with a fresh identifier.
        booking = Booking(booking_id=str(next(self._booking_ids)), screening_id=screening_id, client_id=client_id, row=row, seat=seat)
        # Store the booking so it can be cancelled or queried later.
        self._bookings[booking.booking_id] = booking
        # Return the new booking to the caller.
        return booking

    # Cancel an active booking up to the deadline and refund its price through the gateway.
    def cancel_booking(self, booking_id):
        # Check that the booking exists.
        if booking_id not in self._bookings:
            # Record the rejection before raising it.
            logger.warning("Cancellation rejected: unknown booking %s", booking_id)
            # Reject the cancellation because the booking does not exist.
            raise ProcessingException("Unknown booking")
        # Fetch the booking to cancel.
        booking = self._bookings[booking_id]
        # Check that the booking has not been cancelled already.
        if booking.status != ACTIVE:
            # Record the rejection before raising it.
            logger.warning("Cancellation rejected: booking %s already cancelled", booking_id)
            # Reject the cancellation because the booking is no longer active.
            raise ProcessingException("Booking already cancelled")
        # Fetch the screening to learn its start time and price.
        screening = self._screenings[booking.screening_id]
        # Read the current time from the clock.
        now = self._clock()
        # Check that the cancellation is at least two hours before the start.
        if now > screening.start_time - CANCELLATION_DEADLINE:
            # Record the rejection before raising it.
            logger.warning("Cancellation rejected: booking %s is inside the cancellation deadline", booking_id)
            # Reject the cancellation because the deadline has passed.
            raise ProcessingException("Cancellation deadline passed")
        # Assume the refund fails unless the gateway accepts it.
        outcome = REFUND_FAILED
        # Make the first refund attempt plus up to MAX_TRANSIENT_RETRIES retries.
        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            # Guard the gateway call so its failures are logged and translated.
            try:
                # Ask the gateway to refund the screening price.
                self._gateway.refund(booking_id, screening.price_cents)
                # Record that the gateway accepted the refund.
                outcome = REFUND_REFUNDED
                # Stop retrying because the refund succeeded.
                break
            # Handle a failure that may succeed on retry.
            except TransientPaymentError:
                # Record the transient failure; the loop retries while attempts remain.
                logger.warning("Refund transiently failed for booking %s (attempt %s)", booking_id, attempt + 1)
            # Handle a failure that must not be retried.
            except PermanentPaymentError:
                # Record the permanent failure.
                logger.error("Refund permanently failed for booking %s", booking_id)
                # Stop retrying because the gateway refused for good.
                break
            # Handle a gateway that cannot be reached.
            except PaymentGatewayUnavailableError:
                # Record that the gateway was unavailable.
                logger.error("Refund gateway unavailable; cancellation of booking %s rejected", booking_id)
                # Reject the cancellation so the client can try again later.
                raise ProcessingException("Refund gateway unavailable")
        # Store the refund outcome on the booking.
        booking.refund_status = outcome
        # Check whether the refund was accepted.
        if outcome == REFUND_REFUNDED:
            # Mark the booking cancelled now that its refund is accepted.
            booking.status = CANCELLED
        # Handle a refund that did not go through.
        else:
            # Record that the booking remains active because its refund failed.
            logger.error("Refund failed for booking %s; booking remains active", booking_id)
            # Reject the cancellation and leave the booking active.
            raise ProcessingException("Refund failed; booking remains active")

    # Report the refund status of a booking; unknown bookings are rejected.
    def get_refund_status(self, booking_id):
        # Check that the booking exists.
        if booking_id not in self._bookings:
            # Record the rejection before raising it.
            logger.warning("Refund status rejected: unknown booking %s", booking_id)
            # Reject the query because the booking does not exist.
            raise ProcessingException("Unknown booking")
        # Return the refund status stored on the booking.
        return self._bookings[booking_id].refund_status
