"""Seat booking: rooms with rows and seats, screenings, and seat bookings."""

from dataclasses import dataclass


class SeatAlreadyBookedException(Exception):
    """Raised when booking a seat that is already booked for a screening."""


class UnknownSeatException(Exception):
    """Raised when a seat does not exist in the room of the screening."""


class UnknownScreeningException(Exception):
    """Raised when a screening id is not registered."""


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows of `seats_per_row` seats (1-based numbering)."""

    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat")

    def has_seat(self, row, seat):
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row

    def seats(self):
        return [(r, s) for r in range(1, self.rows + 1) for s in range(1, self.seats_per_row + 1)]


@dataclass(frozen=True)
class Screening:
    """A film shown in a room."""

    screening_id: str
    film: str
    room: Room


class BookingManager:
    """Registers screenings, books seats and reports seat availability."""

    def __init__(self):
        self._screenings = {}
        # screening_id -> {(row, seat): client}
        self._bookings = {}

    def add_screening(self, screening):
        if screening.screening_id in self._screenings:
            raise ValueError("screening already registered: %s" % screening.screening_id)
        self._screenings[screening.screening_id] = screening
        self._bookings[screening.screening_id] = {}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningException(screening_id) from None

    def book_seat(self, screening_id, row, seat, client):
        """Book a seat for a client. Rejects unknown and already booked seats."""
        screening = self._get_screening(screening_id)
        if not screening.room.has_seat(row, seat):
            raise UnknownSeatException((row, seat))
        bookings = self._bookings[screening_id]
        if (row, seat) in bookings:
            raise SeatAlreadyBookedException((row, seat))
        bookings[(row, seat)] = client

    def seat_availability(self, screening_id):
        """Return {(row, seat): True if available} for every seat of the screening."""
        screening = self._get_screening(screening_id)
        bookings = self._bookings[screening_id]
        return {rs: rs not in bookings for rs in screening.room.seats()}
