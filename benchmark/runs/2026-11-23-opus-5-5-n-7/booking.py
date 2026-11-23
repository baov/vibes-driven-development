"""Seat booking for cinema screenings."""

import threading
from dataclasses import dataclass


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
    row: str
    number: int


@dataclass(frozen=True)
class Room:
    """A room laid out as rows, each holding a given number of seats (numbered from 1)."""

    name: str
    seats_per_row: dict  # row label -> seat count, in display order

    def __post_init__(self):
        if not self.seats_per_row:
            raise ValueError("a room needs at least one row")
        for row, count in self.seats_per_row.items():
            if not isinstance(count, int) or count < 1:
                raise ValueError(f"row {row!r} must have a positive number of seats")

    def seats(self):
        return [
            Seat(row, number)
            for row, count in self.seats_per_row.items()
            for number in range(1, count + 1)
        ]

    def has_seat(self, seat):
        count = self.seats_per_row.get(seat.row)
        return count is not None and 1 <= seat.number <= count


@dataclass(frozen=True)
class Screening:
    id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    seat: Seat
    client_id: str


class BookingService:
    """In-memory booking service. Safe to call from multiple threads."""

    def __init__(self):
        self._screenings = {}
        self._bookings = {}  # (screening_id, seat) -> Booking
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening

    def book(self, screening_id, seat, client_id):
        """Book `seat` for `client_id`. Raises SeatAlreadyBookedError if taken."""
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(
                    f"seat {seat.row}{seat.number} does not exist in room {screening.room.name!r}"
                )
            key = (screening_id, seat)
            if key in self._bookings:
                raise SeatAlreadyBookedError(
                    f"seat {seat.row}{seat.number} is already booked for screening {screening_id!r}"
                )
            booking = Booking(screening_id, seat, client_id)
            self._bookings[key] = booking
            return booking

    def availability(self, screening_id):
        """Return {Seat: bool} for every seat of the screening; True means available."""
        with self._lock:
            screening = self._get_screening(screening_id)
            return {
                seat: (screening_id, seat) not in self._bookings
                for seat in screening.room.seats()
            }

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
