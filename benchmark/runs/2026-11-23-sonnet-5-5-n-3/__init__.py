"""Seat booking for cinema screenings (in-memory, standard library only)."""

import threading
from dataclasses import dataclass, field


class BookingError(Exception):
    """Base class for booking errors."""


class UnknownScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


@dataclass(frozen=True)
class Seat:
    row: int  # 1-based
    number: int  # 1-based, within the row


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows of `seats_per_row` seats."""

    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def seats(self):
        return [Seat(r, n) for r in range(1, self.rows + 1) for n in range(1, self.seats_per_row + 1)]

    def contains(self, seat):
        return 1 <= seat.row <= self.rows and 1 <= seat.number <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    id: str
    movie: str
    room: Room


@dataclass
class BookingService:
    _screenings: dict = field(default_factory=dict)
    _bookings: dict = field(default_factory=dict)  # screening id -> {Seat: client}
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def _screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None

    def book(self, screening_id, seat, client):
        """Book `seat` for `client`; raise SeatAlreadyBookedError if taken."""
        with self._lock:
            screening = self._screening(screening_id)
            if not screening.room.contains(seat):
                raise InvalidSeatError(f"{seat} does not exist in room {screening.room.name!r}")
            booked = self._bookings[screening_id]
            if seat in booked:
                raise SeatAlreadyBookedError(f"{seat} is already booked for screening {screening_id!r}")
            booked[seat] = client

    def availability(self, screening_id):
        """Return {Seat: bool} for every seat of the screening (True = available)."""
        with self._lock:
            screening = self._screening(screening_id)
            booked = self._bookings[screening_id]
            return {seat: seat not in booked for seat in screening.room.seats()}
