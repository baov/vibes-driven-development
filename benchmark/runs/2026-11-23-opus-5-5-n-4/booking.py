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


class Room:
    """A room made of named rows, each with seats numbered from 1."""

    def __init__(self, name, rows):
        # rows: mapping of row label -> number of seats, in display order.
        if not rows:
            raise ValueError("a room needs at least one row")
        for label, count in rows.items():
            if not isinstance(count, int) or count < 1:
                raise ValueError(f"row {label!r} must have at least one seat")
        self.name = name
        self._rows = dict(rows)

    def seats(self):
        """All seats of the room, row by row, in seat-number order."""
        return [
            Seat(label, number)
            for label, count in self._rows.items()
            for number in range(1, count + 1)
        ]

    def has_seat(self, seat):
        count = self._rows.get(seat.row)
        return count is not None and 1 <= seat.number <= count


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


class BookingService:
    """Books seats for screenings and reports their availability."""

    def __init__(self):
        self._screenings = {}
        # screening_id -> {Seat: client_id}
        self._bookings = {}
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.screening_id in self._screenings:
                raise ValueError(f"screening {screening.screening_id!r} already exists")
            self._screenings[screening.screening_id] = screening
            self._bookings[screening.screening_id] = {}

    def book(self, screening_id, row, number, client_id):
        """Book one seat for a client. Rejects seats that are already booked."""
        seat = Seat(row, number)
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(
                    f"seat {row}{number} does not exist in room {screening.room.name!r}"
                )
            bookings = self._bookings[screening_id]
            if seat in bookings:
                raise SeatAlreadyBookedError(
                    f"seat {row}{number} is already booked for screening {screening_id!r}"
                )
            bookings[seat] = client_id
            return seat

    def availability(self, screening_id):
        """Map every seat of the screening's room to True if free, False if booked.

        Keys are ordered row by row, then by seat number.
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            bookings = self._bookings[screening_id]
            return {seat: seat not in bookings for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
