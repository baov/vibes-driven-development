"""Seat booking for cinema screenings."""

from dataclasses import dataclass
import threading


class BookingError(Exception):
    """Base class for booking failures."""


class UnknownScreeningError(BookingError):
    pass


class UnknownSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


@dataclass(frozen=True)
class Seat:
    row: int
    number: int


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows of `seats_per_row` seats, numbered from 1."""

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
        self._screenings = {}
        self._bookings = {}  # screening id -> {Seat: client}
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def book(self, screening_id, client, row, number):
        """Book a seat for a client; reject it if already booked."""
        with self._lock:
            screening = self._get_screening(screening_id)
            seat = Seat(row, number)
            if seat not in screening.room.seats():
                raise UnknownSeatError(f"no seat {row}/{number} in room {screening.room.name!r}")
            booked = self._bookings[screening_id]
            if seat in booked:
                raise SeatAlreadyBookedError(f"seat {row}/{number} is already booked")
            booked[seat] = client
            return seat

    def availability(self, screening_id):
        """Return {Seat: bool} for every seat of the screening (True = available)."""
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {seat: seat not in booked for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None
