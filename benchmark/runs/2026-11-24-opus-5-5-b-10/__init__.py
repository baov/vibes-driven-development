"""Seat booking for cinema screenings, with cancellation and refund."""

# Standard library logging, so every layer can report the failures it sees.
import logging
# Lock serialises bookings and cancellations so a seat cannot be sold twice.
import threading
# Unique identifiers for bookings.
import uuid
# Dataclasses keep entities as plain data; behaviour lives in the service.
from dataclasses import dataclass
# Time arithmetic for the cancellation deadline.
from datetime import datetime, timedelta
# Decimal, not float, so prices and refunds are exact.
from decimal import Decimal
# Enum for the booking and refund states.
from enum import Enum
# Type hints for the injected collaborators.
from typing import Callable, Dict, Optional, Protocol, Tuple

# Module logger.
logger = logging.getLogger(__name__)

# A booking can be cancelled up to this long before the screening starts.
CANCELLATION_NOTICE = timedelta(hours=2)
# Number of retries after the first refund attempt fails transiently.
MAX_REFUND_RETRIES = 3


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProcessingException(Exception):
    """Base class for every error raised by the booking service."""


class ScreeningNotFoundError(ProcessingException):
    """The screening id is not known to the service."""


class InvalidSeatError(ProcessingException):
    """The requested seat does not exist in the screening's room."""


class SeatAlreadyBookedError(ProcessingException):
    """The seat already has an active booking for this screening."""


class BookingNotFoundError(ProcessingException):
    """The booking id is not known to the service."""


class BookingAlreadyCancelledError(ProcessingException):
    """The booking was already cancelled."""


class CancellationDeadlinePassedError(ProcessingException):
    """Less than two hours remain before the screening starts."""


class RefundUnavailableError(ProcessingException):
    """The payment gateway is unavailable; the cancellation was rejected."""


class RefundFailedError(ProcessingException):
    """The refund failed (permanently, or after exhausting retries); the booking stays active."""


# Errors the payment gateway raises. Gateway implementations must use these.


class GatewayTransientError(Exception):
    """A temporary gateway failure; the refund may succeed if retried."""


class GatewayPermanentError(Exception):
    """A definitive refusal from the gateway; retrying will not help."""


class GatewayUnavailableError(Exception):
    """The gateway cannot be reached at all."""


class PaymentGateway(Protocol):
    """Interface of the payment gateway passed to the service."""

    def refund(self, booking_id: str, amount: Decimal) -> None:
        """Refund `amount` for `booking_id`, or raise one of the Gateway*Error classes."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


class BookingStatus(Enum):
    """Lifecycle of a booking."""

    # The seat is held by this booking.
    ACTIVE = "active"
    # The booking was cancelled and refunded; the seat is free again.
    CANCELLED = "cancelled"


class RefundStatus(Enum):
    """Outcome of the refund attempted for a booking."""

    # No refund has been attempted (or the gateway was unavailable).
    NOT_REQUESTED = "not_requested"
    # The gateway confirmed the refund.
    REFUNDED = "refunded"
    # The last refund attempt failed; the booking is still active.
    FAILED = "failed"


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows of `seats_per_row` seats, numbered from 1."""

    # Room name, for display.
    name: str
    # Number of rows.
    rows: int
    # Number of seats in each row.
    seats_per_row: int


@dataclass(frozen=True)
class Screening:
    """A film shown in a room at a given time and price."""

    # Screening identifier.
    screening_id: str
    # When the screening starts.
    start: datetime
    # Room where it takes place.
    room: Room
    # Price of one seat.
    price: Decimal


@dataclass
class Booking:
    """A seat booked by a client for a screening."""

    # Booking identifier.
    booking_id: str
    # Screening the seat is booked for.
    screening_id: str
    # Client who made the booking.
    client_id: str
    # Seat row, starting at 1.
    row: int
    # Seat number within the row, starting at 1.
    seat: int
    # Price paid, refunded on cancellation.
    price: Decimal
    # Whether the booking is active or cancelled.
    status: BookingStatus = BookingStatus.ACTIVE
    # Outcome of the refund, if one was attempted.
    refund_status: RefundStatus = RefundStatus.NOT_REQUESTED


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BookingService:
    """Books seats for screenings and cancels them with a refund."""

    def __init__(
        self,
        payment_gateway: PaymentGateway,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        # Gateway used to refund cancelled bookings.
        self._payment_gateway = payment_gateway
        # Source of the current time, injectable for tests.
        self._clock = clock
        # Known screenings, by id.
        self._screenings: Dict[str, Screening] = {}
        # Every booking ever made, by id.
        self._bookings: Dict[str, Booking] = {}
        # Active booking id per (screening id, row, seat).
        self._active_seats: Dict[Tuple[str, int, int], str] = {}
        # Guards the dictionaries above.
        self._lock = threading.Lock()

    def add_screening(self, screening: Screening) -> None:
        """Register a screening so its seats can be booked."""
        # Store the screening under its id.
        with self._lock:
            # Replace any previous definition with the same id.
            self._screenings[screening.screening_id] = screening

    def book_seat(self, screening_id: str, client_id: str, row: int, seat: int) -> Booking:
        """Book a seat for a client. Rejects unknown screenings, invalid seats and seats already booked."""
        with self._lock:
            # Look up the screening.
            screening = self._screenings.get(screening_id)
            # Reject unknown screenings.
            if screening is None:
                # Log, then raise.
                logger.warning("Booking rejected: unknown screening %s", screening_id)
                raise ScreeningNotFoundError(f"Unknown screening {screening_id!r}")
            # Reject seats outside the room.
            if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                # Log, then raise.
                logger.warning("Booking rejected: seat %s-%s not in room %s", row, seat, screening.room.name)
                raise InvalidSeatError(f"Seat {row}-{seat} does not exist in room {screening.room.name!r}")
            # Key identifying the seat for this screening.
            seat_key = (screening_id, row, seat)
            # Reject seats that already have an active booking.
            if seat_key in self._active_seats:
                # Log, then raise.
                logger.warning("Booking rejected: seat %s-%s already booked for %s", row, seat, screening_id)
                raise SeatAlreadyBookedError(f"Seat {row}-{seat} is already booked for screening {screening_id!r}")
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
            self._active_seats[seat_key] = booking.booking_id
            # Hand the booking back to the caller.
            return booking

    def cancel_booking(self, booking_id: str) -> Booking:
        """Cancel a booking and refund it.

        Rejected when the booking is unknown, already cancelled, or less than two hours
        before the screening. Transient gateway failures are retried up to three times.
        A permanent failure (or exhausted retries) marks the refund as failed and leaves
        the booking active. An unavailable gateway rejects the cancellation unchanged.
        """
        with self._lock:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # Reject unknown bookings.
            if booking is None:
                # Log, then raise.
                logger.warning("Cancellation rejected: unknown booking %s", booking_id)
                raise BookingNotFoundError(f"Unknown booking {booking_id!r}")
            # Reject bookings that were already cancelled.
            if booking.status is BookingStatus.CANCELLED:
                # Log, then raise.
                logger.warning("Cancellation rejected: booking %s already cancelled", booking_id)
                raise BookingAlreadyCancelledError(f"Booking {booking_id!r} is already cancelled")
            # Screening the booking belongs to.
            screening = self._screenings[booking.screening_id]
            # Reject cancellations made after the deadline.
            if self._clock() > screening.start - CANCELLATION_NOTICE:
                # Log, then raise.
                logger.warning("Cancellation rejected: booking %s is past the deadline", booking_id)
                raise CancellationDeadlinePassedError(
                    f"Booking {booking_id!r} can only be cancelled up to two hours before the screening"
                )
            # Refund, retrying transient failures; failures leave the booking active.
            self._refund(booking)
            # The refund went through: cancel the booking.
            booking.status = BookingStatus.CANCELLED
            # Free the seat.
            del self._active_seats[(booking.screening_id, booking.row, booking.seat)]
            # Hand the cancelled booking back to the caller.
            return booking

    def refund_status(self, booking_id: str) -> RefundStatus:
        """Return the refund status of a booking."""
        with self._lock:
            # Look up the booking.
            booking = self._bookings.get(booking_id)
            # Reject unknown bookings.
            if booking is None:
                # Log, then raise.
                logger.warning("Refund status requested for unknown booking %s", booking_id)
                raise BookingNotFoundError(f"Unknown booking {booking_id!r}")
            # Report the stored status.
            return booking.refund_status

    def _refund(self, booking: Booking) -> None:
        """Call the gateway, retrying transient failures. Updates `booking.refund_status`."""
        # Last transient error seen, reported if every attempt fails.
        last_error: Optional[GatewayTransientError] = None
        # First attempt plus MAX_REFUND_RETRIES retries.
        for attempt in range(1, MAX_REFUND_RETRIES + 2):
            try:
                # Ask the gateway to refund the price paid.
                self._payment_gateway.refund(booking.booking_id, booking.price)
            except GatewayTransientError as exc:
                # Log and try again.
                logger.warning("Refund attempt %d for booking %s failed transiently: %s", attempt, booking.booking_id, exc)
                # Remember the error in case it was the last attempt.
                last_error = exc
                continue
            except GatewayPermanentError as exc:
                # Log the definitive refusal.
                logger.error("Refund for booking %s failed permanently: %s", booking.booking_id, exc)
                # Record the failure; the booking stays active.
                booking.refund_status = RefundStatus.FAILED
                raise RefundFailedError(f"Refund for booking {booking.booking_id!r} failed permanently") from exc
            except GatewayUnavailableError as exc:
                # Log the outage; nothing is recorded on the booking.
                logger.error("Refund for booking %s rejected: gateway unavailable: %s", booking.booking_id, exc)
                raise RefundUnavailableError(
                    f"Payment gateway unavailable; booking {booking.booking_id!r} was not cancelled"
                ) from exc
            # The gateway accepted the refund.
            booking.refund_status = RefundStatus.REFUNDED
            return
        # Every attempt failed transiently: treat as a failed refund.
        logger.error("Refund for booking %s failed after %d retries", booking.booking_id, MAX_REFUND_RETRIES)
        # Record the failure; the booking stays active.
        booking.refund_status = RefundStatus.FAILED
        raise RefundFailedError(
            f"Refund for booking {booking.booking_id!r} failed after {MAX_REFUND_RETRIES} retries"
        ) from last_error
