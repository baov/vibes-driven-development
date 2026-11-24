"""Seat booking for screenings, with cancellation and refund through a payment gateway."""

# Standard-library logger used to record every rejected or failed operation.
import logging
# Dataclasses give us the plain value types for rooms, screenings and bookings.
from dataclasses import dataclass, field
# Timestamps and the cancellation window are expressed with datetime and timedelta.
from datetime import datetime, timedelta
# Decimal keeps prices exact; binary floats cannot represent most cent amounts.
from decimal import Decimal
# Enum gives the refund status a closed set of values.
from enum import Enum
# itertools.count produces sequential booking identifiers.
import itertools

# Module logger, named after the package so applications can configure it.
logger = logging.getLogger(__name__)

# A booking can be cancelled while at least this much time remains before the screening.
CANCELLATION_CUTOFF = timedelta(hours=2)
# Number of retries after the first refund attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

# Common base for every error raised by this package, so callers can catch them all at once.
class ProcessingException(Exception):
    pass


# Raised when a screening id is not known to the manager.
class ScreeningNotFoundError(ProcessingException):
    pass


# Raised when the requested row or seat does not exist in the screening's room.
class InvalidSeatError(ProcessingException):
    pass


# Raised when the seat already holds an active booking for that screening.
class SeatAlreadyBookedError(ProcessingException):
    pass


# Raised when a booking id is not known to the manager.
class BookingNotFoundError(ProcessingException):
    pass


# Raised when cancelling a booking that has already been cancelled.
class BookingAlreadyCancelledError(ProcessingException):
    pass


# Raised when cancelling less than two hours before the screening starts.
class CancellationWindowClosedError(ProcessingException):
    pass


# Raised when the gateway is unavailable: the cancellation is rejected and nothing changes.
class RefundUnavailableError(ProcessingException):
    pass


# Raised when the refund failed permanently (or transient retries ran out): the booking stays active.
class RefundFailedError(ProcessingException):
    pass


# Errors a payment gateway raises; gateway implementations must use these to signal failures.

# A failure that may succeed if the same refund is attempted again.
class GatewayTransientError(Exception):
    pass


# A failure that will not succeed on retry (e.g. card closed, refund refused).
class GatewayPermanentError(Exception):
    pass


# The gateway cannot be reached or is down; no refund was attempted.
class GatewayUnavailableError(Exception):
    pass


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

# Refund outcome of a booking, as exposed to clients.
class RefundStatus(Enum):
    # No refund has been attempted, or the last attempt was rejected because the gateway was unavailable.
    NOT_REQUESTED = "not_requested"
    # The gateway confirmed the refund; the booking is cancelled.
    REFUNDED = "refunded"
    # The refund failed permanently; the booking is still active.
    FAILED = "failed"


# A room is a grid of `rows` rows, each holding `seats_per_row` seats, both numbered from 1.
@dataclass(frozen=True)
class Room:
    # Human-readable room name.
    name: str
    # Number of rows in the room.
    rows: int
    # Number of seats in each row.
    seats_per_row: int


# A screening happens in one room at one start time, with one seat price.
@dataclass(frozen=True)
class Screening:
    # Identifier used to book seats for this screening.
    screening_id: str
    # When the screening starts; compared with the manager's clock.
    start_time: datetime
    # Room in which the screening takes place.
    room: Room
    # Price charged, and refunded, per seat.
    price: Decimal


# A client's booking of one seat for one screening.
@dataclass
class Booking:
    # Identifier returned to the client.
    booking_id: str
    # Screening the seat belongs to.
    screening_id: str
    # Client who made the booking.
    client_id: str
    # Row of the booked seat.
    row: int
    # Seat number within the row.
    seat: int
    # Amount paid, and therefore the amount to refund.
    price: Decimal
    # False once the booking has been cancelled and refunded.
    active: bool = True
    # Outcome of the most recent refund attempt.
    refund_status: RefundStatus = field(default=RefundStatus.NOT_REQUESTED)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

# In-memory booking service: books seats, cancels bookings and refunds them through the gateway.
class BookingManager:
    """Coordinates screenings, bookings and refunds.

    `payment_gateway` must provide `refund(booking_id, amount)` and signal failures by raising
    GatewayTransientError, GatewayPermanentError or GatewayUnavailableError.
    `clock` returns the current time; it must be comparable with screening start times.
    """

    def __init__(self, payment_gateway, clock=datetime.now):
        # Gateway used to refund cancelled bookings.
        self._payment_gateway = payment_gateway
        # Time source, injectable so the cancellation window can be tested deterministically.
        self._clock = clock
        # Known screenings by id.
        self._screenings = {}
        # Every booking ever made, by id, including cancelled ones.
        self._bookings = {}
        # Active booking id for each occupied seat, keyed by (screening_id, row, seat).
        self._occupied_seats = {}
        # Source of sequential booking ids.
        self._booking_ids = itertools.count(1)

    def add_screening(self, screening):
        # Register the screening so seats can be booked for it.
        self._screenings[screening.screening_id] = screening

    def book_seat(self, client_id, screening_id, row, seat):
        """Book a seat and return the new Booking.

        Raises ScreeningNotFoundError, InvalidSeatError or SeatAlreadyBookedError.
        """
        # Look up the screening; an unknown id cannot be booked.
        screening = self._screenings.get(screening_id)
        # Reject bookings for screenings that were never added.
        if screening is None:
            # Record the rejection before raising it.
            logger.warning("Booking rejected: unknown screening %s", screening_id)
            # Tell the caller which screening was not found.
            raise ScreeningNotFoundError(f"Unknown screening {screening_id!r}")
        # Reject seats outside the room's grid.
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            # Record the rejection before raising it.
            logger.warning("Booking rejected: seat %s-%s does not exist in screening %s", row, seat, screening_id)
            # Tell the caller which seat is invalid.
            raise InvalidSeatError(f"Seat {row}-{seat} does not exist in room {screening.room.name!r}")
        # Key identifying this seat for this screening.
        seat_key = (screening_id, row, seat)
        # Reject a seat that already holds an active booking.
        if seat_key in self._occupied_seats:
            # Record the rejection before raising it.
            logger.warning("Booking rejected: seat %s-%s already booked for screening %s", row, seat, screening_id)
            # Tell the caller the seat is taken.
            raise SeatAlreadyBookedError(f"Seat {row}-{seat} is already booked for screening {screening_id!r}")
        # Create the booking at the screening's current price.
        booking = Booking(
            booking_id=f"B{next(self._booking_ids)}",
            screening_id=screening_id,
            client_id=client_id,
            row=row,
            seat=seat,
            price=screening.price,
        )
        # Store the booking so it can be cancelled and queried later.
        self._bookings[booking.booking_id] = booking
        # Mark the seat as taken by this booking.
        self._occupied_seats[seat_key] = booking.booking_id
        # Hand the booking back to the caller.
        return booking

    def cancel_booking(self, booking_id):
        """Cancel a booking and refund it. Returns the cancelled Booking.

        Raises BookingNotFoundError, BookingAlreadyCancelledError, CancellationWindowClosedError,
        RefundUnavailableError (nothing changed) or RefundFailedError (booking stays active).
        """
        # Look up the booking; unknown ids are rejected.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            # Record the rejection before raising it.
            logger.warning("Cancellation rejected: unknown booking %s", booking_id)
            # Tell the caller which booking was not found.
            raise BookingNotFoundError(f"Unknown booking {booking_id!r}")
        # Reject a second cancellation of the same booking.
        if not booking.active:
            # Record the rejection before raising it.
            logger.warning("Cancellation rejected: booking %s is already cancelled", booking_id)
            # Tell the caller the booking was already cancelled.
            raise BookingAlreadyCancelledError(f"Booking {booking_id!r} is already cancelled")
        # Screening the booking belongs to, needed for its start time.
        screening = self._screenings[booking.screening_id]
        # Cancellation is allowed up to and including exactly two hours before the start.
        if self._clock() > screening.start_time - CANCELLATION_CUTOFF:
            # Record the rejection before raising it.
            logger.warning("Cancellation rejected: booking %s is within two hours of the screening", booking_id)
            # Tell the caller the window has closed.
            raise CancellationWindowClosedError(
                f"Booking {booking_id!r} can no longer be cancelled: the screening starts at {screening.start_time}"
            )

        # One initial attempt plus up to MAX_REFUND_RETRIES retries on transient failures.
        for attempt in range(1, MAX_REFUND_RETRIES + 2):
            try:
                # Ask the gateway to refund the amount paid.
                self._payment_gateway.refund(booking.booking_id, booking.price)
            except GatewayTransientError as error:
                # Record the transient failure so repeated retries are visible.
                logger.warning("Refund attempt %s for booking %s failed transiently: %s", attempt, booking_id, error)
                # Try again while retries remain.
                if attempt <= MAX_REFUND_RETRIES:
                    continue
                # Retries exhausted: treat as a permanent failure; the booking stays active.
                booking.refund_status = RefundStatus.FAILED
                # Record the final failure before raising it.
                logger.error("Refund for booking %s failed after %s attempts", booking_id, attempt)
                # Tell the caller the refund failed, keeping the gateway error as the cause.
                raise RefundFailedError(
                    f"Refund for booking {booking_id!r} failed after {attempt} attempts; the booking is still active"
                ) from error
            except GatewayPermanentError as error:
                # The refund will not succeed; the booking stays active.
                booking.refund_status = RefundStatus.FAILED
                # Record the failure before raising it.
                logger.error("Refund for booking %s failed permanently: %s", booking_id, error)
                # Tell the caller the refund failed, keeping the gateway error as the cause.
                raise RefundFailedError(
                    f"Refund for booking {booking_id!r} failed; the booking is still active"
                ) from error
            except GatewayUnavailableError as error:
                # Record the rejection before raising it; booking and refund status are left unchanged.
                logger.warning("Cancellation rejected: payment gateway unavailable for booking %s: %s", booking_id, error)
                # Tell the caller the cancellation was rejected, keeping the gateway error as the cause.
                raise RefundUnavailableError(
                    f"Payment gateway unavailable; booking {booking_id!r} was not cancelled"
                ) from error
            # The refund succeeded: stop retrying.
            break

        # Mark the booking as cancelled.
        booking.active = False
        # Record the successful refund.
        booking.refund_status = RefundStatus.REFUNDED
        # Free the seat so it can be booked again.
        del self._occupied_seats[(booking.screening_id, booking.row, booking.seat)]
        # Hand the cancelled booking back to the caller.
        return booking

    def get_refund_status(self, booking_id):
        """Return the RefundStatus of a booking. Raises BookingNotFoundError for unknown ids."""
        # Look up the booking; unknown ids are rejected.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            # Record the rejection before raising it.
            logger.warning("Refund status rejected: unknown booking %s", booking_id)
            # Tell the caller which booking was not found.
            raise BookingNotFoundError(f"Unknown booking {booking_id!r}")
        # Report the outcome of the most recent refund attempt.
        return booking.refund_status
