"""Seat booking for screenings."""
import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for booking errors."""


class SeatAlreadyBookedError(BookingError):
    pass


class UnknownScreeningError(BookingError):
    pass


class UnknownSeatError(BookingError):
    pass


@dataclass(frozen=True)
class Seat:
    row: int
    number: int


@dataclass(frozen=True)
class Room:
    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def seats(self):
        return [Seat(r, n) for r in range(1, self.rows + 1)
                for n in range(1, self.seats_per_row + 1)]


@dataclass(frozen=True)
class Screening:
    id: str
    film: str
    room: Room


class BookingService:
    def __init__(self):
        self._lock = threading.Lock()
        self._screenings = {}
        self._bookings = {}  # screening id -> {Seat: client}

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

    def book(self, screening_id, client, row, number):
        """Book a seat for a client; reject it if already booked."""
        with self._lock:
            screening = self._screening(screening_id)
            seat = Seat(row, number)
            if seat not in screening.room.seats():
                raise UnknownSeatError("no seat %s in room %s" % (seat, screening.room.name))
            booked = self._bookings[screening_id]
            if seat in booked:
                raise SeatAlreadyBookedError(seat)
            booked[seat] = client
            return seat

    def availability(self, screening_id):
        """Return {Seat: True if available} for every seat of the screening."""
        with self._lock:
            screening = self._screening(screening_id)
            booked = self._bookings[screening_id]
            return {s: s not in booked for s in screening.room.seats()}
