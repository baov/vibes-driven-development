"""Seat booking for cinema screenings.

A ``Room`` has named rows, each holding a number of seats numbered from 1.
A ``Screening`` takes place in a room. ``BookingService`` lets a client book a
seat for a screening, rejects double bookings, and reports the availability of
every seat of a screening.
"""

import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for booking errors."""


class UnknownScreeningError(BookingError):
    """The screening is not registered with the service."""


class DuplicateScreeningError(BookingError):
    """A screening with the same id is already registered."""


class InvalidSeatError(BookingError):
    """The seat does not exist in the screening's room."""


class SeatAlreadyBookedError(BookingError):
    """The seat is already booked for this screening."""


@dataclass(frozen=True)
class Seat:
    row: str
    number: int


@dataclass(frozen=True)
class Room:
    """A room with ordered rows; ``rows`` is a sequence of (row label, seat count)."""

    name: str
    rows: tuple

    def __init__(self, name, rows):
        rows = tuple((str(label), int(count)) for label, count in rows)
        labels = [label for label, _ in rows]
        if len(set(labels)) != len(labels):
            raise ValueError("row labels must be unique")
        if any(count < 1 for _, count in rows):
            raise ValueError("each row must have at least one seat")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "rows", rows)

    def seats(self):
        """All seats of the room, in row order then seat number order."""
        return [Seat(label, n) for label, count in self.rows for n in range(1, count + 1)]

    def has_seat(self, seat):
        return any(label == seat.row and 1 <= seat.number <= count for label, count in self.rows)


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    seat: Seat
    client_id: str


class BookingService:
    """In-memory booking service. Safe to use from several threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._screenings = {}
        # screening_id -> {Seat: Booking}
        self._bookings = {}

    def add_screening(self, screening):
        with self._lock:
            if screening.screening_id in self._screenings:
                raise DuplicateScreeningError(screening.screening_id)
            self._screenings[screening.screening_id] = screening
            self._bookings[screening.screening_id] = {}

    def book(self, screening_id, row, number, client_id):
        """Book seat (row, number) of a screening for a client.

        Raises UnknownScreeningError, InvalidSeatError or SeatAlreadyBookedError.
        """
        seat = Seat(str(row), number)
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise InvalidSeatError(f"{seat} does not exist in room {screening.room.name}")
            bookings = self._bookings[screening_id]
            if seat in bookings:
                raise SeatAlreadyBookedError(f"{seat} is already booked for screening {screening_id}")
            booking = Booking(screening_id, seat, client_id)
            bookings[seat] = booking
            return booking

    def availability(self, screening_id):
        """Map every seat of the screening's room to True if free, False if booked.

        The mapping is ordered by row, then by seat number.
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {seat: seat not in booked for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None
