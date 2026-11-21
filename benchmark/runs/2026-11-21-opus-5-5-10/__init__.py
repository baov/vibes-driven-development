"""Seat booking for cinema screenings.

A screening takes place in a room made of rows of seats. A client books one
seat of a screening; a seat can be booked only once per screening. The manager
also reports the availability of every seat of a screening.
"""

# Import dataclass to declare the plain data records below.
from dataclasses import dataclass
# Import logging so rejected bookings are observable.
import logging
# Import threading so the check-then-book sequence is atomic.
import threading

# Create the module logger.
logger = logging.getLogger(__name__)


# Base class for every error raised by the booking manager.
class BookingError(Exception):
    """Base class for seat booking errors."""


# Raised when a screening id is unknown or registered twice.
class ScreeningError(BookingError):
    """The screening does not exist, or already exists."""


# Raised when the requested row or seat does not exist in the room.
class SeatNotFoundError(BookingError):
    """The seat does not exist in the screening's room."""


# Raised when the requested seat is already booked for the screening.
class SeatAlreadyBookedError(BookingError):
    """The seat is already booked for this screening."""


# Plain data record describing a room: row label -> number of seats in that row.
@dataclass(frozen=True)
class Room:
    # Room name, for display.
    name: str
    # Ordered mapping of row label to seat count; seats are numbered from 1.
    rows: dict


# Plain data record describing a screening held in a room.
@dataclass(frozen=True)
class Screening:
    # Unique screening identifier.
    screening_id: str
    # Room where the screening takes place.
    room: Room


# Plain data record describing a confirmed booking.
@dataclass(frozen=True)
class Booking:
    # Screening the seat was booked for.
    screening_id: str
    # Row label of the booked seat.
    row: str
    # Seat number within the row, starting at 1.
    seat: int
    # Client who booked the seat.
    client_id: str


# Holds screenings and their bookings, and enforces one booking per seat.
class SeatBookingManager:
    """In-memory seat booking service."""

    def __init__(self):
        # Map screening id -> Screening.
        self._screenings = {}
        # Map screening id -> {(row, seat): Booking}.
        self._bookings = {}
        # Lock guarding both maps so concurrent bookings cannot double-book.
        self._lock = threading.Lock()

    def add_screening(self, screening):
        """Register a screening. Raises ScreeningError if the id is taken."""
        # Serialize access to the shared maps.
        with self._lock:
            # Reject a duplicate screening id, which would silently drop bookings.
            if screening.screening_id in self._screenings:
                # Signal the duplicate to the caller.
                raise ScreeningError(
                    f"screening {screening.screening_id!r} already exists"
                )
            # Store the screening.
            self._screenings[screening.screening_id] = screening
            # Start it with no bookings.
            self._bookings[screening.screening_id] = {}

    def book_seat(self, screening_id, row, seat, client_id):
        """Book one seat for a client and return the Booking.

        Raises ScreeningError for an unknown screening, SeatNotFoundError for a
        seat outside the room, and SeatAlreadyBookedError if the seat is taken.
        """
        # Serialize the check and the write so two clients cannot both win.
        with self._lock:
            # Resolve the screening, failing on an unknown id.
            screening = self._get_screening(screening_id)
            # Look up how many seats the requested row has (None if no such row).
            seat_count = screening.room.rows.get(row)
            # Reject rows absent from the room and seat numbers outside 1..seat_count.
            if seat_count is None or not 1 <= seat <= seat_count:
                # Signal the invalid seat to the caller.
                raise SeatNotFoundError(
                    f"seat {row}{seat} does not exist in room {screening.room.name!r}"
                )
            # Fetch the bookings already made for this screening.
            bookings = self._bookings[screening_id]
            # Reject the request if the seat is already taken.
            if (row, seat) in bookings:
                # Record the rejection for observability.
                logger.warning(
                    "rejected booking of seat %s%s for screening %s by client %s: already booked",
                    row, seat, screening_id, client_id,
                )
                # Signal the conflict to the caller.
                raise SeatAlreadyBookedError(
                    f"seat {row}{seat} is already booked for screening {screening_id!r}"
                )
            # Build the booking record.
            booking = Booking(screening_id, row, seat, client_id)
            # Mark the seat as taken.
            bookings[(row, seat)] = booking
            # Hand the confirmed booking back to the caller.
            return booking

    def get_seat_availability(self, screening_id):
        """Return {row: {seat_number: is_available}} for every seat of the screening.

        Rows keep the room's order; seats are listed from 1 upward.
        """
        # Read under the lock so the snapshot is consistent.
        with self._lock:
            # Resolve the screening, failing on an unknown id.
            screening = self._get_screening(screening_id)
            # Fetch the bookings made for this screening.
            bookings = self._bookings[screening_id]
            # Build one entry per row and seat, True when nobody booked it.
            return {
                row: {
                    seat: (row, seat) not in bookings
                    for seat in range(1, seat_count + 1)
                }
                for row, seat_count in screening.room.rows.items()
            }

    def _get_screening(self, screening_id):
        # Look up the screening (None if unknown).
        screening = self._screenings.get(screening_id)
        # Reject unknown screening ids.
        if screening is None:
            # Signal the unknown screening to the caller.
            raise ScreeningError(f"screening {screening_id!r} does not exist")
        # Return the resolved screening.
        return screening
