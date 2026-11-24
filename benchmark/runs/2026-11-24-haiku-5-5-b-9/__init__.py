# Imports the counter that hands out booking ids
import itertools
# Imports the logger used to record every failure before it is raised
import logging
# Imports the decorator that turns plain classes into data holders
from dataclasses import dataclass
# Imports the time types used for start times and the cancellation cutoff
from datetime import datetime, timedelta, timezone

# Creates the logger for this module
logger = logging.getLogger(__name__)

# Sets how long before the start a booking can still be cancelled
CANCELLATION_CUTOFF = timedelta(hours=2)
# Sets how many times a transient refund failure is retried after the first attempt
MAX_REFUND_RETRIES = 3
# Names the status of a booking that holds its seat
ACTIVE = "ACTIVE"
# Names the status of a booking whose seat was released
CANCELLED = "CANCELLED"
# Names the refund status of a booking that has not been refunded or attempted
NOT_REQUESTED = "NOT_REQUESTED"
# Names the refund status of a booking whose refund went through
REFUNDED = "REFUNDED"
# Names the refund status of a booking whose refund failed
REFUND_FAILED = "REFUND_FAILED"


# Signals a refund failure that a retry may fix
class GatewayTransientError(Exception):
    # Carries no extra behaviour
    pass


# Signals a refund failure that a retry will not fix
class GatewayPermanentError(Exception):
    # Carries no extra behaviour
    pass


# Signals that the payment gateway cannot be reached right now
class GatewayUnavailableError(Exception):
    # Carries no extra behaviour
    pass


# Generic exception raised at the service boundary so gateway details do not leak out
class ProcessingException(Exception):
    # Carries no extra behaviour
    pass


# Plain data for a screening: a start time, a room of rows and seats, and a price
@dataclass
class Screening:
    # Identifies the screening
    screening_id: int
    # Start time, must be timezone-aware
    start_time: datetime
    # Number of rows in the room
    rows: int
    # Number of seats in each row
    seats_per_row: int
    # Full price in integer cents
    price_cents: int


# Plain data for a booking of one seat on one screening
@dataclass
class Booking:
    # Identifies the booking
    booking_id: int
    # Screening the seat belongs to
    screening_id: int
    # Row of the seat
    row: int
    # Seat number within the row
    seat_number: int
    # ACTIVE while the seat is held, CANCELLED afterwards
    status: str
    # NOT_REQUESTED, REFUNDED or REFUND_FAILED
    refund_status: str


# Owns screenings and bookings, and runs the booking, cancellation and refund flow
class SeatBookingManager:
    # Stores the payment gateway and the clock; the clock defaults to the real UTC time
    def __init__(self, payment_gateway, clock=None):
        # Keeps the gateway used for refunds
        self._payment_gateway = payment_gateway
        # Keeps a clock returning the current aware time, real UTC unless one is given
        self._clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        # Holds screenings keyed by screening id
        self._screenings = {}
        # Holds bookings keyed by booking id
        self._bookings = {}
        # Hands out increasing booking ids starting at 1
        self._booking_ids = itertools.count(1)

    # Registers a screening so seats can be booked for it
    def add_screening(self, screening):
        # Stores the screening under its id
        self._screenings[screening.screening_id] = screening

    # Books one seat for a screening and returns the new booking id
    def book_seat(self, screening_id, row, seat_number):
        # Looks up the screening to know the room layout
        screening = self._screenings.get(screening_id)
        # Checks that the screening exists
        if screening is None:
            # Records the rejection
            logger.warning("Booking rejected: unknown screening %s", screening_id)
            # Rejects the booking
            raise ProcessingException("Unknown screening")
        # Checks that the seat exists in the room
        if not (1 <= row <= screening.rows and 1 <= seat_number <= screening.seats_per_row):
            # Records the rejection
            logger.warning("Booking rejected: seat %s,%s does not exist in screening %s", row, seat_number, screening_id)
            # Rejects the booking
            raise ProcessingException("Seat does not exist in this room")
        # Walks through the existing bookings looking for an active one on the same seat
        for booking in self._bookings.values():
            # Compares the booking with the requested seat and checks it is still held
            if booking.screening_id == screening_id and booking.row == row and booking.seat_number == seat_number and booking.status == ACTIVE:
                # Records the rejection
                logger.warning("Booking rejected: seat %s,%s already booked for screening %s", row, seat_number, screening_id)
                # Rejects the booking
                raise ProcessingException("Seat already booked")
        # Creates an active booking with the next id and no refund requested
        booking = Booking(booking_id=next(self._booking_ids), screening_id=screening_id, row=row, seat_number=seat_number, status=ACTIVE, refund_status=NOT_REQUESTED)
        # Stores the new booking
        self._bookings[booking.booking_id] = booking
        # Returns the id of the new booking
        return booking.booking_id

    # Cancels an active booking up to two hours before its start and refunds its full price
    def cancel_booking(self, booking_id):
        # Looks up the booking
        booking = self._bookings.get(booking_id)
        # Checks that the booking exists
        if booking is None:
            # Records the rejection
            logger.warning("Cancellation rejected: unknown booking %s", booking_id)
            # Rejects the cancellation
            raise ProcessingException("Unknown booking")
        # Checks that the booking has not already been cancelled
        if booking.status == CANCELLED:
            # Records the rejection
            logger.warning("Cancellation rejected: booking %s already cancelled", booking_id)
            # Rejects the cancellation
            raise ProcessingException("Booking already cancelled")
        # Looks up the screening to know the start time and the price
        screening = self._screenings[booking.screening_id]
        # Checks that at least the cutoff remains before the screening starts
        if screening.start_time - self._clock() < CANCELLATION_CUTOFF:
            # Records the rejection
            logger.warning("Cancellation rejected: booking %s is within the cancellation cutoff", booking_id)
            # Rejects the cancellation
            raise ProcessingException("Too late to cancel")
        # Tries the refund once, then retries it on transient failures
        for attempt in range(1, MAX_REFUND_RETRIES + 2):
            # Guards the gateway call so every gateway failure is handled here
            try:
                # Sends the full price back through the gateway
                self._payment_gateway.refund(booking.booking_id, screening.price_cents)
            # Handles a refund failure that a retry may fix
            except GatewayTransientError as exc:
                # Records the transient failure
                logger.warning("Refund attempt %s for booking %s failed transiently", attempt, booking_id, exc_info=exc)
                # Checks whether retries are exhausted
                if attempt > MAX_REFUND_RETRIES:
                    # Marks the refund as failed while the booking stays active
                    booking.refund_status = REFUND_FAILED
                    # Records the failure after exhausting retries
                    logger.error("Refund for booking %s failed after %s attempts", booking_id, attempt)
                    # Rejects the cancellation and hides the gateway details
                    raise ProcessingException("Refund failed after retries") from exc
            # Handles a refund failure that a retry will not fix
            except GatewayPermanentError as exc:
                # Marks the refund as failed while the booking stays active
                booking.refund_status = REFUND_FAILED
                # Records the permanent failure
                logger.error("Refund for booking %s failed permanently", booking_id, exc_info=exc)
                # Rejects the cancellation and hides the gateway details
                raise ProcessingException("Refund failed permanently") from exc
            # Handles a gateway that cannot be reached
            except GatewayUnavailableError as exc:
                # Records the unavailability
                logger.error("Refund gateway unavailable for booking %s", booking_id, exc_info=exc)
                # Rejects the cancellation and leaves the refund status untouched
                raise ProcessingException("Refund gateway unavailable, cancellation rejected") from exc
            # Runs only when the refund went through
            else:
                # Releases the seat
                booking.status = CANCELLED
                # Records that the refund went through
                booking.refund_status = REFUNDED
                # Ends the cancellation
                return

    # Returns the refund status of a booking
    def get_refund_status(self, booking_id):
        # Looks up the booking
        booking = self._bookings.get(booking_id)
        # Checks that the booking exists
        if booking is None:
            # Records the rejection
            logger.warning("Refund status lookup rejected: unknown booking %s", booking_id)
            # Rejects the lookup
            raise ProcessingException("Unknown booking")
        # Returns the refund status of the booking
        return booking.refund_status
