"""Seat booking for screenings, with cancellation and refund through a payment gateway."""

import itertools
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Callable, Dict, Optional, Tuple

# Module logger, so every failure on the refund path leaves a trace.
logger = logging.getLogger(__name__)

# A booking can be cancelled up to (and including) this delay before the screening starts.
CANCELLATION_DEADLINE = timedelta(hours=2)
# Number of retries after the first refund attempt when the gateway fails transiently.
MAX_REFUND_RETRIES = 3


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

# Base class for every rejection raised by BookingManager (AGENTS.md: ProcessingException at the boundary).
class ProcessingException(Exception):
    pass


# Raised when the requested seat does not exist in the screening's room.
class InvalidSeatError(ProcessingException):
    pass


# Raised when the requested seat already has an active booking for this screening.
class SeatAlreadyBookedError(ProcessingException):
    pass


# Raised when the screening id is not known to the manager.
class UnknownScreeningError(ProcessingException):
    pass


# Raised when the booking id is not known to the manager.
class UnknownBookingError(ProcessingException):
    pass


# Raised when cancelling a booking that is already cancelled.
class BookingAlreadyCancelledError(ProcessingException):
    pass


# Raised when cancelling later than CANCELLATION_DEADLINE before the screening starts.
class CancellationDeadlinePassedError(ProcessingException):
    pass


# Raised when the gateway is unavailable: the cancellation is rejected and nothing changes.
class RefundGatewayUnavailableError(ProcessingException):
    pass


# Raised when the refund failed for good: the booking stays active and its refund status is FAILED.
class RefundFailedError(ProcessingException):
    pass


# Errors a payment gateway raises from refund(); gateway implementations must use these.
class GatewayError(Exception):
    pass


# The refund may succeed if attempted again.
class TransientGatewayError(GatewayError):
    pass


# The refund will never succeed for this request.
class PermanentGatewayError(GatewayError):
    pass


# The gateway cannot be reached at all.
class GatewayUnavailableError(GatewayError):
    pass


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

# Room layout: rows numbered 1..rows, seats numbered 1..seats_per_row in every row.
@dataclass(frozen=True)
class Room:
    name: str
    rows: int
    seats_per_row: int


# A screening of a film in a room, at a start time, for a price per seat.
@dataclass(frozen=True)
class Screening:
    screening_id: str
    start_time: datetime
    room: Room
    price: Decimal


# Lifecycle of a booking.
class BookingStatus(Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


# Outcome of the refund attached to a booking.
class RefundStatus(Enum):
    NOT_REQUESTED = "not_requested"
    REFUNDED = "refunded"
    FAILED = "failed"


# A client's booking of one seat for one screening.
@dataclass
class Booking:
    booking_id: str
    screening_id: str
    client_id: str
    row: int
    seat: int
    price: Decimal
    status: BookingStatus = BookingStatus.ACTIVE
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class BookingManager:
    """Books seats, cancels bookings and refunds them through `payment_gateway`.

    `payment_gateway` must expose `refund(booking_id, amount)` and raise one of
    TransientGatewayError, PermanentGatewayError or GatewayUnavailableError on failure.
    `clock` returns the current datetime; it is injectable for tests.
    """

    def __init__(self, payment_gateway, clock: Callable[[], datetime] = datetime.now):
        # Gateway used for every refund.
        self._payment_gateway = payment_gateway
        # Source of the current time for the cancellation deadline.
        self._clock = clock
        # Known screenings by id.
        self._screenings: Dict[str, Screening] = {}
        # All bookings ever made, by id, including cancelled ones.
        self._bookings: Dict[str, Booking] = {}
        # Active booking id per (screening_id, row, seat), to detect double booking.
        self._active_seats: Dict[Tuple[str, int, int], str] = {}
        # Sequence for booking ids.
        self._booking_ids = itertools.count(1)

    def add_screening(self, screening: Screening) -> None:
        # Register (or replace) the screening so it can be booked.
        self._screenings[screening.screening_id] = screening

    def book_seat(self, screening_id: str, client_id: str, row: int, seat: int) -> Booking:
        # Look up the screening; unknown ids are rejected.
        screening = self._screenings.get(screening_id)
        # Reject bookings for a screening that was never registered.
        if screening is None:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}")
        # Reject seats outside the room layout.
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            raise InvalidSeatError(f"seat row={row} seat={seat} does not exist in room {screening.room.name!r}")
        # Key identifying this seat for this screening.
        seat_key = (screening_id, row, seat)
        # Reject the seat if another active booking holds it.
        if seat_key in self._active_seats:
            raise SeatAlreadyBookedError(f"seat row={row} seat={seat} is already booked for {screening_id!r}")
        # Create the booking at the screening's current price.
        booking = Booking(
            booking_id=f"B{next(self._booking_ids)}",
            screening_id=screening_id,
            client_id=client_id,
            row=row,
            seat=seat,
            price=screening.price,
        )
        # Store the booking.
        self._bookings[booking.booking_id] = booking
        # Mark the seat as taken.
        self._active_seats[seat_key] = booking.booking_id
        # Hand the booking back to the caller.
        return booking

    def cancel_booking(self, booking_id: str) -> Booking:
        # Look up the booking; unknown ids are rejected.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            raise UnknownBookingError(f"unknown booking {booking_id!r}")
        # Reject bookings that were already cancelled.
        if booking.status is BookingStatus.CANCELLED:
            raise BookingAlreadyCancelledError(f"booking {booking_id!r} is already cancelled")
        # Screening the booking belongs to, for the deadline check.
        screening = self._screenings[booking.screening_id]
        # Reject cancellations later than two hours before the start.
        if self._clock() > screening.start_time - CANCELLATION_DEADLINE:
            raise CancellationDeadlinePassedError(
                f"booking {booking_id!r} can no longer be cancelled (screening starts {screening.start_time})"
            )

        # Refund first; the booking is only cancelled once the money is back.
        attempt = 0
        # Retry loop: one initial attempt plus up to MAX_REFUND_RETRIES retries on transient failures.
        while True:
            # Count this attempt.
            attempt += 1
            try:
                # Ask the gateway to refund the booking price.
                self._payment_gateway.refund(booking_id, booking.price)
                # Refund succeeded: leave the loop.
                break
            except TransientGatewayError as error:
                # Log every transient failure, including the ones that will be retried.
                logger.warning("refund of %s failed transiently (attempt %d): %s", booking_id, attempt, error)
                # Retry while retries remain.
                if attempt <= MAX_REFUND_RETRIES:
                    continue
                # Retries exhausted: treat as a definitive failure, the booking stays active.
                booking.refund_status = RefundStatus.FAILED
                # Surface the failure to the caller, keeping the gateway error as cause.
                raise RefundFailedError(
                    f"refund of {booking_id!r} still failing after {MAX_REFUND_RETRIES} retries"
                ) from error
            except PermanentGatewayError as error:
                # Log the permanent failure.
                logger.error("refund of %s failed permanently: %s", booking_id, error)
                # The booking stays active; record the failed refund.
                booking.refund_status = RefundStatus.FAILED
                # Surface the failure to the caller, keeping the gateway error as cause.
                raise RefundFailedError(f"refund of {booking_id!r} failed permanently") from error
            except GatewayUnavailableError as error:
                # Log the unavailability.
                logger.error("refund of %s rejected, gateway unavailable: %s", booking_id, error)
                # Reject the cancellation without touching the booking, keeping the gateway error as cause.
                raise RefundGatewayUnavailableError(
                    f"cancellation of {booking_id!r} rejected: payment gateway unavailable"
                ) from error

        # Mark the refund as done.
        booking.refund_status = RefundStatus.REFUNDED
        # Mark the booking as cancelled.
        booking.status = BookingStatus.CANCELLED
        # Free the seat so it can be booked again.
        del self._active_seats[(booking.screening_id, booking.row, booking.seat)]
        # Hand the updated booking back to the caller.
        return booking

    def get_refund_status(self, booking_id: str) -> RefundStatus:
        # Look up the booking; unknown ids are rejected.
        booking = self._bookings.get(booking_id)
        # Reject unknown bookings.
        if booking is None:
            raise UnknownBookingError(f"unknown booking {booking_id!r}")
        # Report the refund status.
        return booking.refund_status

    def get_booking(self, booking_id: str) -> Optional[Booking]:
        # Return the booking, or None when unknown.
        return self._bookings.get(booking_id)
