"""Seat booking for cinema screenings.

A room has named rows, each with a number of seats (numbered from 1).
A screening takes place in a room. A client books one seat of a screening;
a seat can be booked at most once per screening.
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple


class BookingError(Exception):
    """Base class for every rejection raised by the booking service."""


class UnknownScreeningError(BookingError):
    pass


class DuplicateScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


@dataclass(frozen=True)
class Room:
    room_id: str
    # Row label -> number of seats in that row, e.g. {"A": 10, "B": 12}.
    seats_per_row: Mapping[str, int]

    def __post_init__(self):
        if not self.seats_per_row:
            raise ValueError("a room needs at least one row")
        for row, count in self.seats_per_row.items():
            if not isinstance(count, int) or count < 1:
                raise ValueError(f"row {row!r} must have at least one seat")
        # Copy so later mutation of the caller's dict cannot reshape the room.
        object.__setattr__(self, "seats_per_row", dict(self.seats_per_row))

    def has_seat(self, row: str, seat: int) -> bool:
        count = self.seats_per_row.get(row)
        return count is not None and isinstance(seat, int) and 1 <= seat <= count


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    row: str
    seat: int
    client_id: str


@dataclass(frozen=True)
class SeatAvailability:
    row: str
    seat: int
    available: bool


@dataclass
class BookingManager:
    """In-memory booking service. Thread-safe: check-and-book is atomic."""

    _screenings: Dict[str, Screening] = field(default_factory=dict)
    _bookings: Dict[Tuple[str, str, int], Booking] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_screening(self, screening: Screening) -> None:
        with self._lock:
            if screening.screening_id in self._screenings:
                raise DuplicateScreeningError(
                    f"screening {screening.screening_id!r} already exists"
                )
            self._screenings[screening.screening_id] = screening

    def book_seat(self, screening_id: str, row: str, seat: int, client_id: str) -> Booking:
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(row, seat):
                raise InvalidSeatError(
                    f"seat {row}{seat} does not exist in room {screening.room.room_id!r}"
                )
            key = (screening_id, row, seat)
            if key in self._bookings:
                raise SeatAlreadyBookedError(
                    f"seat {row}{seat} is already booked for screening {screening_id!r}"
                )
            booking = Booking(screening_id, row, seat, client_id)
            self._bookings[key] = booking
            return booking

    def seat_availability(self, screening_id: str) -> List[SeatAvailability]:
        """Every seat of the screening's room, row by row in room order, seats ascending."""
        with self._lock:
            screening = self._get_screening(screening_id)
            return [
                SeatAvailability(row, seat, (screening_id, row, seat) not in self._bookings)
                for row, count in screening.room.seats_per_row.items()
                for seat in range(1, count + 1)
            ]

    def _get_screening(self, screening_id: str) -> Screening:
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
