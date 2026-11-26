"""Seat booking for cinema screenings, with cancellation and refund.

Design notes:
- Prices are ``decimal.Decimal`` so refunded amounts are exact.
- Time is read through an injectable ``clock`` so the two-hour cancellation
  window can be tested deterministically.
- The payment gateway is any object with ``refund(booking_id, amount)``. It
  signals failures by raising one of the three gateway exceptions below.
"""

# Import dataclass helpers to declare the plain data records.
from dataclasses import dataclass, field
# Import datetime types for screening start times and the cancellation window.
from datetime import datetime, timedelta, timezone
# Import Decimal so money amounts are exact.
from decimal import Decimal
# Import Enum to expose a closed set of refund statuses.
from enum import Enum
# Import logging so refund failures are observable.
import logging
# Import threading so seat checks and state changes are atomic.
import threading
# Import uuid to generate booking identifiers.
import uuid

# Create the module logger.
logger = logging.getLogger(__name__)

# Minimum delay between cancellation and screening start.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Number of retries after a transient gateway failure (4 attempts in total).
MAX_REFUND_RETRIES = 3


# --- Errors raised by the payment gateway -----------------------------------

# Declare the base class for gateway-originated failures.
class RefundGatewayError(Exception):
    # Mark the class body as intentionally empty.
    pass


# Declare the failure that may succeed if the call is retried.
class TransientRefundError(RefundGatewayError):
    # Mark the class body as intentionally empty.
    pass


# Declare the failure that will not succeed on retry.
class PermanentRefundError(RefundGatewayError):
    # Mark the class body as intentionally empty.
    pass


# Declare the failure raised when the gateway cannot be reached at all.
class GatewayUnavailableError(RefundGatewayError):
    # Mark the class body as intentionally empty.
    pass


# --- Errors raised by the booking service -----------------------------------

# Declare the base class so callers can catch every booking rejection.
class BookingError(Exception):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection for a screening id that does not exist.
class UnknownScreeningError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection for a row/seat outside the room layout.
class InvalidSeatError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection for a seat that already has an active booking.
class SeatAlreadyBookedError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection for a booking id that does not exist.
class UnknownBookingError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection for a booking that is already cancelled.
class BookingAlreadyCancelledError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection for a cancellation less than two hours before start.
class CancellationWindowClosedError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the rejection used when the gateway is unavailable.
class RefundUnavailableError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# Declare the error raised when the refund definitively failed.
class RefundFailedError(BookingError):
    # Mark the class body as intentionally empty.
    pass


# --- Data records -------------------------------------------------------------

# Enumerate the refund states a booking can be in.
class RefundStatus(Enum):
    # No refund has been attempted (or the gateway was unavailable).
    NOT_REQUESTED = "not_requested"
    # The gateway refunded the booking; the booking is cancelled.
    REFUNDED = "refunded"
    # The gateway refused or kept failing; the booking stays active.
    FAILED = "failed"


# Describe a room as a grid of rows and seats per row.
@dataclass(frozen=True)
class Room:
    # Store the room name.
    name: str
    # Store the number of rows (numbered from 1).
    rows: int
    # Store the number of seats in each row (numbered from 1).
    seats_per_row: int


# Describe a screening of a film in a room at a given time and price.
@dataclass(frozen=True)
class Screening:
    # Store the screening identifier.
    screening_id: str
    # Store the timezone-aware start time.
    starts_at: datetime
    # Store the room where the screening happens.
    room: Room
    # Store the seat price.
    price: Decimal


# Record a client's booking of one seat for one screening.
@dataclass
class Booking:
    # Store the booking identifier.
    booking_id: str
    # Store the booked screening identifier.
    screening_id: str
    # Store the client identifier.
    client_id: str
    # Store the booked row.
    row: int
    # Store the booked seat within the row.
    seat: int
    # Store the price paid, which is the amount to refund.
    price: Decimal
    # Store whether the booking was cancelled.
    cancelled: bool = False
    # Store the refund status, starting with no refund requested.
    refund_status: RefundStatus = field(default=RefundStatus.NOT_REQUESTED)


# --- Service --------------------------------------------------------------------

# Book seats, cancel bookings and refund them through the payment gateway.
class BookingService:

    # Wire the gateway and clock, and create the in-memory stores.
    def __init__(self, payment_gateway, clock=None):
        # Keep the gateway used for refunds.
        self._payment_gateway = payment_gateway
        # Keep the clock, defaulting to the current UTC time.
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Index screenings by id.
        self._screenings = {}
        # Index bookings by id.
        self._bookings = {}
        # Index active booking ids by (screening id, row, seat).
        self._active_seats = {}
        # Serialize state changes so one seat cannot be booked twice.
        self._lock = threading.RLock()

    # Register a screening so seats can be booked for it.
    def add_screening(self, screening):
        # Take the lock while mutating the store.
        with self._lock:
            # Store the screening under its id.
            self._screenings[screening.screening_id] = screening

    # Book a seat for a client; reject unknown screenings, bad seats, and seats already taken.
    def book_seat(self, client_id, screening_id, row, seat):
        # Take the lock so the availability check and the insert are atomic.
        with self._lock:
            # Look up the screening.
            screening = self._screenings.get(screening_id)
            # Reject an unknown screening.
            if screening is None:
                # Raise the rejection with the offending id.
                raise UnknownScreeningError(f"unknown screening {screening_id!r}")
            # Reject a row outside the room.
            if not 1 <= row <= screening.room.rows:
                # Raise the rejection with the offending row.
                raise InvalidSeatError(f"row {row} does not exist in room {screening.room.name!r}")
            # Reject a seat outside the row.
            if not 1 <= seat <= screening.room.seats_per_row:
                # Raise the rejection with the offending seat.
                raise InvalidSeatError(f"seat {seat} does not exist in room {screening.room.name!r}")
            # Build the key identifying this seat for this screening.
            seat_key = (screening_id, row, seat)
            # Reject a seat that already has an active booking.
            if seat_key in self._active_seats:
                # Raise the rejection with the seat coordinates.
                raise SeatAlreadyBookedError(f"row {row} seat {seat} is already booked for {screening_id!r}")
            # Create the booking at the screening's current price.
            booking = Booking(
                # Generate a unique booking id.
                booking_id=str(uuid.uuid4()),
                # Link the booking to the screening.
                screening_id=screening_id,
                # Record the client.
                client_id=client_id,
                # Record the row.
                row=row,
                # Record the seat.
                seat=seat,
                # Record the price to refund later.
                price=screening.price,
            )
            # Store the booking.
            self._bookings[booking.booking_id] = booking
            # Mark the seat as taken.
            self._active_seats[seat_key] = booking.booking_id
            # Return the new booking to the caller.
            return booking

    # Cancel a booking and refund it, retrying transient gateway failures.
    def cancel_booking(self, booking_id):
        # Take the lock so two cancellations of one booking cannot both refund.
        with self._lock:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # Reject an unknown booking.
            if booking is None:
                # Raise the rejection with the offending id.
                raise UnknownBookingError(f"unknown booking {booking_id!r}")
            # Reject a booking that is already cancelled.
            if booking.cancelled:
                # Raise the rejection with the booking id.
                raise BookingAlreadyCancelledError(f"booking {booking_id!r} is already cancelled")
            # Look up the screening to know when it starts.
            screening = self._screenings[booking.screening_id]
            # Reject a cancellation later than two hours before the start.
            if self._clock() > screening.starts_at - CANCELLATION_DEADLINE:
                # Raise the rejection with the booking id.
                raise CancellationWindowClosedError(
                    # Explain the two-hour rule in the message.
                    f"booking {booking_id!r} can no longer be cancelled (less than 2 hours before start)"
                )
            # Attempt the refund once, then retry up to MAX_REFUND_RETRIES times on transient errors.
            for attempt in range(1 + MAX_REFUND_RETRIES):
                # Try the refund.
                try:
                    # Ask the gateway to refund the price paid.
                    self._payment_gateway.refund(booking_id, booking.price)
                # Handle a gateway that cannot be reached.
                except GatewayUnavailableError as error:
                    # Log the rejection with the booking id.
                    logger.warning("refund gateway unavailable for booking %s", booking_id)
                    # Reject the cancellation, leaving booking and refund status untouched.
                    raise RefundUnavailableError(
                        # Explain that the client can try again later.
                        f"payment gateway unavailable, booking {booking_id!r} was not cancelled"
                    ) from error
                # Handle a definitive refusal.
                except PermanentRefundError as error:
                    # Record that the refund failed; the booking stays active.
                    booking.refund_status = RefundStatus.FAILED
                    # Log the failure with the booking id.
                    logger.error("refund permanently failed for booking %s", booking_id)
                    # Report the failure to the caller.
                    raise RefundFailedError(f"refund failed, booking {booking_id!r} stays active") from error
                # Handle a failure that may succeed on retry.
                except TransientRefundError as error:
                    # Log the attempt number for diagnosis.
                    logger.warning("transient refund failure for booking %s (attempt %d)", booking_id, attempt + 1)
                    # Keep the last error to chain it if retries run out.
                    last_error = error
                    # Retry the refund.
                    continue
                # Mark the booking as cancelled once the refund succeeded.
                booking.cancelled = True
                # Record the successful refund.
                booking.refund_status = RefundStatus.REFUNDED
                # Free the seat so it can be booked again.
                del self._active_seats[(booking.screening_id, booking.row, booking.seat)]
                # Return the cancelled booking.
                return booking
            # Record that the refund failed after exhausting retries; the booking stays active.
            booking.refund_status = RefundStatus.FAILED
            # Log the exhaustion with the booking id.
            logger.error("refund failed after %d retries for booking %s", MAX_REFUND_RETRIES, booking_id)
            # Report the failure to the caller.
            raise RefundFailedError(
                # Explain that the retries were exhausted.
                f"refund failed after {MAX_REFUND_RETRIES} retries, booking {booking_id!r} stays active"
            ) from last_error

    # Return the refund status of a booking.
    def refund_status(self, booking_id):
        # Take the lock to read a consistent state.
        with self._lock:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # Reject an unknown booking.
            if booking is None:
                # Raise the rejection with the offending id.
                raise UnknownBookingError(f"unknown booking {booking_id!r}")
            # Return the recorded status.
            return booking.refund_status
