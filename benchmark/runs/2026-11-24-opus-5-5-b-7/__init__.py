"""Seat booking for cinema screenings, with cancellation and refund."""

# Enables postponed evaluation of type annotations.
from __future__ import annotations

# Provides the logger used to report refund failures.
import logging
# Provides the lock that serialises bookings and cancellations.
import threading
# Provides immutable/mutable record types for screenings and bookings.
from dataclasses import dataclass
# Provides timezone-aware time arithmetic for the cancellation deadline.
from datetime import datetime, timedelta, timezone
# Provides exact decimal arithmetic for prices and refunds.
from decimal import Decimal
# Provides the refund status enumeration.
from enum import Enum
# Provides type hints for the injectable clock and the gateway contract.
from typing import Callable, Dict, Protocol, Tuple

# Module logger.
logger = logging.getLogger(__name__)

# Latest point before the screening start at which a booking may be cancelled.
CANCELLATION_CUTOFF = timedelta(hours=2)
# Number of retries after the first refund attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3


# Base class of every error raised by the booking service.
class ProcessingException(Exception):
    """Base class for seat booking errors."""


# Raised when a screening id is not known.
class UnknownScreeningError(ProcessingException):
    """The screening does not exist."""


# Raised when a row/seat pair is outside the screening room.
class InvalidSeatError(ProcessingException):
    """The seat does not exist in the screening room."""


# Raised when booking a seat that already holds an active booking.
class SeatAlreadyBookedError(ProcessingException):
    """The seat is already booked for this screening."""


# Raised when a booking id is not known.
class UnknownBookingError(ProcessingException):
    """The booking does not exist."""


# Raised when cancelling a booking that is already cancelled.
class BookingAlreadyCancelledError(ProcessingException):
    """The booking has already been cancelled."""


# Raised when cancelling later than the cancellation cutoff.
class CancellationDeadlinePassedError(ProcessingException):
    """The booking can no longer be cancelled."""


# Raised when the gateway is unavailable: the cancellation is rejected, nothing changes.
class RefundUnavailableError(ProcessingException):
    """The payment gateway is unavailable; the cancellation was rejected."""


# Raised when the refund failed (permanently or after all retries): the booking stays active.
class RefundFailedError(ProcessingException):
    """The refund failed; the booking stays active."""


# Error a gateway raises for a failure worth retrying.
class TransientGatewayError(Exception):
    """Temporary gateway failure; the call may be retried."""


# Error a gateway raises for a failure that must not be retried.
class PermanentGatewayError(Exception):
    """Definitive gateway failure; retrying will not help."""


# Error a gateway raises when it cannot be reached at all.
class GatewayUnavailableError(Exception):
    """The gateway cannot be reached."""


# Contract the payment gateway passed to the service must fulfil.
class PaymentGateway(Protocol):
    # Refunds `amount` for `booking_id`; the booking id doubles as an idempotency key across retries.
    def refund(self, booking_id: str, amount: Decimal) -> None: ...


# Refund status exposed for each booking.
class RefundStatus(Enum):
    # No refund has been attempted.
    NOT_REQUESTED = "not_requested"
    # The refund succeeded and the booking is cancelled.
    REFUNDED = "refunded"
    # The last refund attempt failed; the booking is still active.
    FAILED = "failed"


# A room is a grid of numbered rows, each with numbered seats (both 1-based).
@dataclass(frozen=True)
class Room:
    # Room name.
    name: str
    # Number of rows in the room.
    rows: int
    # Number of seats in each row.
    seats_per_row: int


# A screening of a film in a room at a given time and price.
@dataclass(frozen=True)
class Screening:
    # Screening identifier.
    screening_id: str
    # Timezone-aware start time.
    starts_at: datetime
    # Room the screening takes place in.
    room: Room
    # Ticket price, refunded in full on cancellation.
    price: Decimal


# A client's booking of one seat for one screening.
@dataclass
class Booking:
    # Booking identifier.
    booking_id: str
    # Screening the seat is booked for.
    screening_id: str
    # Client who booked.
    client_id: str
    # Row number of the seat.
    row: int
    # Seat number within the row.
    seat: int
    # Price paid, captured at booking time.
    price: Decimal
    # Whether the booking has been cancelled.
    cancelled: bool = False
    # Current refund status.
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# Books seats and cancels bookings with a refund through the payment gateway.
class SeatBookingManager:
    # Builds the manager around a gateway and a clock returning timezone-aware datetimes.
    def __init__(
        self,
        payment_gateway: PaymentGateway,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        # Gateway used for refunds.
        self._gateway = payment_gateway
        # Source of the current time.
        self._clock = clock
        # Screenings by id.
        self._screenings: Dict[str, Screening] = {}
        # Bookings by id.
        self._bookings: Dict[str, Booking] = {}
        # Active booking id per (screening, row, seat).
        self._active_seats: Dict[Tuple[str, int, int], str] = {}
        # Counter used to generate booking ids.
        self._next_booking_number = 1
        # Lock making seat checks and cancellations atomic.
        self._lock = threading.Lock()

    # Registers a screening so seats can be booked for it.
    def add_screening(self, screening: Screening) -> None:
        # Rejects naive datetimes, which cannot be compared safely with the clock.
        if screening.starts_at.tzinfo is None:
            # Signals the invalid start time.
            raise ValueError("screening start time must be timezone-aware")
        # Takes the lock before mutating shared state.
        with self._lock:
            # Stores the screening.
            self._screenings[screening.screening_id] = screening

    # Books a seat for a client and returns the new booking.
    def book_seat(self, screening_id: str, client_id: str, row: int, seat: int) -> Booking:
        # Takes the lock so two clients cannot book the same seat concurrently.
        with self._lock:
            # Looks up the screening.
            screening = self._screenings.get(screening_id)
            # Rejects unknown screenings.
            if screening is None:
                # Signals the unknown screening.
                raise UnknownScreeningError(f"unknown screening {screening_id!r}")
            # Rejects seats outside the room grid.
            if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                # Signals the invalid seat.
                raise InvalidSeatError(f"row {row} seat {seat} does not exist in room {screening.room.name!r}")
            # Key identifying the seat for this screening.
            seat_key = (screening_id, row, seat)
            # Rejects a seat that already holds an active booking.
            if seat_key in self._active_seats:
                # Signals the double booking.
                raise SeatAlreadyBookedError(f"row {row} seat {seat} is already booked for {screening_id!r}")
            # Generates the booking id.
            booking_id = f"B{self._next_booking_number}"
            # Advances the id counter.
            self._next_booking_number += 1
            # Creates the booking at the screening's current price.
            booking = Booking(booking_id, screening_id, client_id, row, seat, screening.price)
            # Stores the booking.
            self._bookings[booking_id] = booking
            # Marks the seat as taken.
            self._active_seats[seat_key] = booking_id
            # Returns the booking.
            return booking

    # Cancels a booking and refunds it; on failure the booking stays active.
    def cancel_booking(self, booking_id: str) -> Booking:
        # Holds the lock for the whole cancellation so a booking cannot be refunded twice.
        with self._lock:
            # Looks up the booking.
            booking = self._bookings.get(booking_id)
            # Rejects unknown bookings.
            if booking is None:
                # Signals the unknown booking.
                raise UnknownBookingError(f"unknown booking {booking_id!r}")
            # Rejects bookings that are already cancelled.
            if booking.cancelled:
                # Signals the repeated cancellation.
                raise BookingAlreadyCancelledError(f"booking {booking_id!r} is already cancelled")
            # Looks up the screening the booking belongs to.
            screening = self._screenings[booking.screening_id]
            # Rejects cancellations later than two hours before the start (exactly two hours is allowed).
            if self._clock() > screening.starts_at - CANCELLATION_CUTOFF:
                # Signals the missed deadline.
                raise CancellationDeadlinePassedError(
                    f"booking {booking_id!r} can only be cancelled up to 2 hours before the screening"
                )
            # Tries the first attempt plus up to MAX_REFUND_RETRIES retries on transient failures.
            for attempt in range(1, MAX_REFUND_RETRIES + 2):
                # Calls the gateway and handles each failure mode.
                try:
                    # Requests the refund.
                    self._gateway.refund(booking.booking_id, booking.price)
                # Gateway down: reject the cancellation and leave the booking untouched.
                except GatewayUnavailableError as error:
                    # Records the rejection.
                    logger.warning("refund for %s rejected: gateway unavailable", booking_id)
                    # Signals the rejection, keeping the gateway error as cause.
                    raise RefundUnavailableError(
                        f"payment gateway unavailable; booking {booking_id!r} was not cancelled"
                    ) from error
                # Definitive failure: the booking stays active.
                except PermanentGatewayError as error:
                    # Records the failed refund on the booking.
                    booking.refund_status = RefundStatus.FAILED
                    # Records the failure.
                    logger.error("refund for %s failed permanently", booking_id)
                    # Signals the failure, keeping the gateway error as cause.
                    raise RefundFailedError(f"refund failed; booking {booking_id!r} stays active") from error
                # Temporary failure: retry while attempts remain.
                except TransientGatewayError as error:
                    # Records the transient failure.
                    logger.warning("refund for %s failed transiently (attempt %d)", booking_id, attempt)
                    # Gives up once the retries are exhausted.
                    if attempt > MAX_REFUND_RETRIES:
                        # Records the failed refund on the booking.
                        booking.refund_status = RefundStatus.FAILED
                        # Signals the failure, keeping the last gateway error as cause.
                        raise RefundFailedError(
                            f"refund failed after {MAX_REFUND_RETRIES} retries; booking {booking_id!r} stays active"
                        ) from error
                # Refund succeeded: stop retrying.
                else:
                    # Leaves the retry loop.
                    break
            # Marks the booking as cancelled.
            booking.cancelled = True
            # Records the successful refund.
            booking.refund_status = RefundStatus.REFUNDED
            # Frees the seat for new bookings.
            del self._active_seats[(booking.screening_id, booking.row, booking.seat)]
            # Returns the cancelled booking.
            return booking

    # Exposes the refund status of a booking.
    def get_refund_status(self, booking_id: str) -> RefundStatus:
        # Reads under the lock for a consistent view.
        with self._lock:
            # Looks up the booking.
            booking = self._bookings.get(booking_id)
            # Rejects unknown bookings.
            if booking is None:
                # Signals the unknown booking.
                raise UnknownBookingError(f"unknown booking {booking_id!r}")
            # Returns the status.
            return booking.refund_status
