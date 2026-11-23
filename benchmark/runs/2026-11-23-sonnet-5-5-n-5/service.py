"""Seat booking: rooms, screenings and bookings, in one module."""

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
    row: int
    number: int


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows, each having the given number of seats."""

    name: str
    seats_per_row: tuple

    def __post_init__(self):
        if not self.seats_per_row or any(n < 1 for n in self.seats_per_row):
            raise ValueError("a room needs at least one row, each with at least one seat")

    def seats(self):
        return [
            Seat(r, n)
            for r, count in enumerate(self.seats_per_row, start=1)
            for n in range(1, count + 1)
        ]


@dataclass(frozen=True)
class Screening:
    id: str
    film: str
    room: Room


class BookingService:
    def __init__(self):
        self._screenings = {}
        # screening id -> {Seat: client}
        self._bookings = {}

    def add_screening(self, screening):
        if screening.id in self._screenings:
            raise ValueError(f"screening {screening.id!r} already exists")
        self._screenings[screening.id] = screening
        self._bookings[screening.id] = {}

    def _screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None

    def book(self, screening_id, client, row, number):
        """Book a seat for a client; raises SeatAlreadyBookedError if taken."""
        screening = self._screening(screening_id)
        seat = Seat(row, number)
        if seat not in screening.room.seats():
            raise UnknownSeatError(seat)
        bookings = self._bookings[screening_id]
        if seat in bookings:
            raise SeatAlreadyBookedError(seat)
        bookings[seat] = client
        return seat

    def availability(self, screening_id):
        """Return {Seat: True if available} for every seat of the screening."""
        screening = self._screening(screening_id)
        bookings = self._bookings[screening_id]
        return {seat: seat not in bookings for seat in screening.room.seats()}
