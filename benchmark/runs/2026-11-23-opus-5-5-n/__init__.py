"""Seat booking for cinema screenings.

A screening takes place in a room made of rows of seats. A client books one
seat of a screening; a seat can be booked only once per screening.
"""

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
    """A room whose rows may hold different numbers of seats.

    `rows` maps a row label to its seat count; seats are numbered from 1.
    """

    def __init__(self, name, rows):
        if not rows:
            raise ValueError("a room needs at least one row")
        for label, count in rows.items():
            if count < 1:
                raise ValueError(f"row {label!r} needs at least one seat")
        self.name = name
        self.rows = dict(rows)

    def seats(self):
        """All seats, in row order then seat number order."""
        return [
            Seat(label, number)
            for label, count in self.rows.items()
            for number in range(1, count + 1)
        ]

    def has_seat(self, seat):
        count = self.rows.get(seat.row)
        return count is not None and 1 <= seat.number <= count


@dataclass(frozen=True)
class Screening:
    id: str
    room: Room


class BookingService:
    def __init__(self):
        self._screenings = {}
        # screening id -> {Seat: client id}
        self._bookings = {}
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def book(self, screening_id, row, number, client_id):
        """Book a seat for a client. Raises SeatAlreadyBookedError if taken."""
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
        """Map every seat of the screening's room to True if it is free."""
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {seat: seat not in booked for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(
                f"unknown screening {screening_id!r}"
            ) from None
