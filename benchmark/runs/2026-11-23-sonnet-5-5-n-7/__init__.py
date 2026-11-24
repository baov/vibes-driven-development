"""Seat booking for cinema screenings."""
import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for booking failures."""


class UnknownScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows of `seats_per_row` seats (1-indexed)."""
    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat")

    def seats(self):
        return [(r, s) for r in range(1, self.rows + 1)
                for s in range(1, self.seats_per_row + 1)]


@dataclass(frozen=True)
class Screening:
    id: str
    film: str
    room: Room


class BookingService:
    def __init__(self):
        self._screenings = {}
        self._bookings = {}  # screening id -> {(row, seat): client}
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError("screening already exists: %s" % screening.id)
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def _screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None

    def book(self, screening_id, client, row, seat):
        """Book a seat; raises SeatAlreadyBookedError if it is taken."""
        with self._lock:
            room = self._screening(screening_id).room
            if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
                raise InvalidSeatError((row, seat))
            booked = self._bookings[screening_id]
            if (row, seat) in booked:
                raise SeatAlreadyBookedError((row, seat))
            booked[(row, seat)] = client

    def availability(self, screening_id):
        """Return {(row, seat): True if available} for every seat."""
        with self._lock:
            screening = self._screening(screening_id)
            booked = self._bookings[screening_id]
            return {s: s not in booked for s in screening.room.seats()}
