"""Seat booking for cinema screenings.

A room has numbered rows (1..rows), each with numbered seats (1..seats_per_row).
A screening takes place in one room. A client books one seat of one screening;
a seat can be booked at most once per screening.
"""

import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for booking failures a caller is expected to handle."""


class UnknownRoomError(BookingError):
    pass


class UnknownScreeningError(BookingError):
    pass


class SeatNotFoundError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


@dataclass(frozen=True)
class Room:
    room_id: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def has_seat(self, row, seat):
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


@dataclass(frozen=True)
class SeatAvailability:
    row: int
    seat: int
    available: bool


class SeatBookingManager:
    """In-memory booking service. Safe to call from several threads."""

    def __init__(self):
        self._rooms = {}
        self._screening_rooms = {}
        # screening_id -> {(row, seat): client_id}
        self._bookings = {}
        self._lock = threading.Lock()

    def add_room(self, room):
        with self._lock:
            self._rooms[room.room_id] = room

    def add_screening(self, screening_id, room_id):
        with self._lock:
            if room_id not in self._rooms:
                raise UnknownRoomError(f"unknown room {room_id!r}")
            if screening_id in self._screening_rooms:
                raise ValueError(f"screening {screening_id!r} already exists")
            self._screening_rooms[screening_id] = self._rooms[room_id]
            self._bookings[screening_id] = {}

    def book_seat(self, screening_id, row, seat, client_id):
        """Book (row, seat) of a screening for a client.

        Raises SeatAlreadyBookedError if the seat is taken, whoever took it.
        The check and the write happen under one lock, so two concurrent
        requests for the same seat cannot both succeed.
        """
        with self._lock:
            room = self._room_of(screening_id)
            if not room.has_seat(row, seat):
                raise SeatNotFoundError(
                    f"seat {row}-{seat} does not exist in room {room.room_id!r}"
                )
            bookings = self._bookings[screening_id]
            if (row, seat) in bookings:
                raise SeatAlreadyBookedError(
                    f"seat {row}-{seat} is already booked for screening {screening_id!r}"
                )
            bookings[(row, seat)] = client_id

    def seat_availability(self, screening_id):
        """Return every seat of the screening's room, ordered by row then seat."""
        with self._lock:
            room = self._room_of(screening_id)
            booked = set(self._bookings[screening_id])
        return [
            SeatAvailability(row, seat, (row, seat) not in booked)
            for row in range(1, room.rows + 1)
            for seat in range(1, room.seats_per_row + 1)
        ]

    def _room_of(self, screening_id):
        try:
            return self._screening_rooms[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
