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
    """A room laid out as named rows, each with seats numbered 1..n."""

    name: str
    seats_per_row: dict  # row label -> number of seats in that row

    def __post_init__(self):
        if not self.seats_per_row:
            raise ValueError("a room must have at least one row")
        for row, count in self.seats_per_row.items():
            if not isinstance(count, int) or count < 1:
                raise ValueError(f"row {row!r} must have at least one seat")
        # Freeze the layout so a shared Room cannot be mutated after use.
        object.__setattr__(self, "seats_per_row", dict(self.seats_per_row))

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
    """Books seats for screenings; a seat can be booked once per screening."""

    def __init__(self):
        self._screenings = {}
        self._bookings = {}  # screening id -> {Seat: Booking}
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def book(self, screening_id, seat, client_id):
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(
                    f"seat {seat.row}{seat.number} does not exist in room {screening.room.name!r}"
                )
            bookings = self._bookings[screening_id]
            if seat in bookings:
                raise SeatAlreadyBookedError(
                    f"seat {seat.row}{seat.number} is already booked for screening {screening_id!r}"
                )
            booking = Booking(screening_id, seat, client_id)
            bookings[seat] = booking
            return booking

    def availability(self, screening_id):
        """Return {Seat: bool} for every seat of the screening's room, True if free."""
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {seat: seat not in booked for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
