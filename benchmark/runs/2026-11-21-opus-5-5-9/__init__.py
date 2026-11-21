"""Seat reservation service for a cinema chain."""

# Import dataclass to declare plain data entities.
from dataclasses import dataclass, field
# Import logging so every failure is observable.
import logging
# Import threading so check-then-book is atomic under concurrent clients.
import threading

# Module-level logger used by every layer of this module.
logger = logging.getLogger(__name__)
# Library convention: emit nothing unless the application configures logging.
logger.addHandler(logging.NullHandler())


# Base error raised at this module's boundary.
class ProcessingException(Exception):
    # Docstring describing the role of the exception.
    """Raised when the booking service cannot process a request."""


# Specific error so callers can tell a rejected double booking apart.
class SeatAlreadyBookedException(ProcessingException):
    # Docstring describing the role of the exception.
    """Raised when a client tries to book a seat that is already booked."""


# Specific error for references to rows, seats or screenings that do not exist.
class UnknownSeatException(ProcessingException):
    # Docstring describing the role of the exception.
    """Raised when a screening or seat does not exist."""


# Room entity: a named room made of rows, each with a number of seats.
@dataclass(frozen=True)
class Room:
    # Identifier of the room.
    room_id: str
    # Mapping of row label to the number of seats in that row (seats are numbered from 1).
    rows: dict


# Screening entity: a showing that takes place in a room.
@dataclass
class Screening:
    # Identifier of the screening.
    screening_id: str
    # Room in which the screening takes place.
    room: Room
    # Bookings keyed by (row, seat) and valued by client id.
    bookings: dict = field(default_factory=dict)


# Service holding screenings and handling bookings and availability.
class SeatBookingManager:
    # Docstring describing the role of the manager.
    """Books seats for screenings and reports seat availability."""

    # Initialise an empty registry of screenings.
    def __init__(self):
        # Screenings keyed by screening id.
        self._screenings = {}
        # Lock guarding every read-modify-write on bookings.
        self._lock = threading.Lock()

    # Register a screening taking place in a room.
    def add_screening(self, screening_id, room):
        # Guard registry updates with the lock.
        with self._lock:
            # Refuse to silently overwrite an existing screening and its bookings.
            if screening_id in self._screenings:
                # Log the rejected registration before raising.
                logger.warning("Screening %s already exists", screening_id)
                # Reject the duplicate registration.
                raise ProcessingException(f"Screening {screening_id} already exists")
            # Create and store the screening with no bookings.
            self._screenings[screening_id] = Screening(screening_id, room)

    # Book one seat of a screening for a client.
    def book_seat(self, screening_id, row, seat, client_id):
        # Guard the check-then-book sequence so two clients cannot book the same seat.
        with self._lock:
            # Resolve and validate the screening and seat.
            screening = self._get_screening_and_check_seat(screening_id, row, seat)
            # Reject the booking if the seat is already taken.
            if (row, seat) in screening.bookings:
                # Log the rejected booking before raising.
                logger.warning("Seat %s%s of screening %s is already booked", row, seat, screening_id)
                # Reject the double booking.
                raise SeatAlreadyBookedException(
                    f"Seat {row}{seat} of screening {screening_id} is already booked"
                )
            # Record the booking for this client.
            screening.bookings[(row, seat)] = client_id

    # Report whether each seat of a screening is available.
    def get_availability(self, screening_id):
        # Read under the lock to get a consistent snapshot.
        with self._lock:
            # Resolve the screening, rejecting unknown ids.
            screening = self._get_screening(screening_id)
            # Map every (row, seat) of the room to True when free, False when booked.
            return {
                (row, seat): (row, seat) not in screening.bookings
                for row, seat_count in screening.room.rows.items()
                for seat in range(1, seat_count + 1)
            }

    # Look up a screening, raising when it does not exist (caller holds the lock).
    def _get_screening(self, screening_id):
        # Translate the lookup failure into this module's exception.
        try:
            # Return the registered screening.
            return self._screenings[screening_id]
        # Missing key means the screening is unknown.
        except KeyError as error:
            # Log the failure at this layer.
            logger.warning("Unknown screening %s", screening_id)
            # Rethrow as a module exception, keeping the cause for debugging.
            raise UnknownSeatException(f"Unknown screening {screening_id}") from error

    # Look up a screening and check the seat exists in its room (caller holds the lock).
    def _get_screening_and_check_seat(self, screening_id, row, seat):
        # Resolve the screening first.
        screening = self._get_screening(screening_id)
        # Number of seats in the requested row, or None when the row does not exist.
        seat_count = screening.room.rows.get(row)
        # Reject unknown rows and seat numbers outside 1..seat_count.
        if seat_count is None or not isinstance(seat, int) or not 1 <= seat <= seat_count:
            # Log the failure at this layer.
            logger.warning("Seat %s%s does not exist in screening %s", row, seat, screening_id)
            # Reject the invalid seat.
            raise UnknownSeatException(f"Seat {row}{seat} does not exist in screening {screening_id}")
        # Return the validated screening.
        return screening
