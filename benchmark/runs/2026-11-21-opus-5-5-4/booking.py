"""Seat booking for cinema screenings.

A Room has named rows, each holding a number of seats (numbered from 1).
A Screening takes place in a Room. A client books one seat of a screening;
a seat can be booked at most once per screening.
"""

from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Mapping, Tuple


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
    name: str
    # Ordered mapping: row label -> number of seats in that row.
    rows: Mapping[str, int]

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("a room needs at least one row")
        for label, count in self.rows.items():
            if count < 1:
                raise ValueError(f"row {label!r} must have at least one seat")

    def seats(self) -> List[Seat]:
        return [
            Seat(label, number)
            for label, count in self.rows.items()
            for number in range(1, count + 1)
        ]

    def has_seat(self, seat: Seat) -> bool:
        count = self.rows.get(seat.row)
        return count is not None and 1 <= seat.number <= count


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


@dataclass(frozen=True)
class SeatAvailability:
    seat: Seat
    available: bool


class BookingService:
    """In-memory booking service. Safe to call from several threads."""

    def __init__(self) -> None:
        self._screenings: Dict[str, Screening] = {}
        # screening_id -> {seat: client_id}
        self._bookings: Dict[str, Dict[Seat, str]] = {}
        self._lock = Lock()

    def add_screening(self, screening: Screening) -> None:
        with self._lock:
            if screening.screening_id in self._screenings:
                raise ValueError(
                    f"screening {screening.screening_id!r} already exists"
                )
            self._screenings[screening.screening_id] = screening
            self._bookings[screening.screening_id] = {}

    def book(self, screening_id: str, seat: Seat, client_id: str) -> None:
        """Book `seat` for `client_id`.

        Raises UnknownScreeningError, UnknownSeatError, or
        SeatAlreadyBookedError if the seat is taken (by anyone, including
        the same client).
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(
                    f"seat {seat.row}{seat.number} does not exist in room "
                    f"{screening.room.name!r}"
                )
            bookings = self._bookings[screening_id]
            if seat in bookings:
                raise SeatAlreadyBookedError(
                    f"seat {seat.row}{seat.number} is already booked for "
                    f"screening {screening_id!r}"
                )
            bookings[seat] = client_id

    def availability(self, screening_id: str) -> List[SeatAvailability]:
        """Every seat of the screening's room, in row then seat order."""
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = set(self._bookings[screening_id])
            return [
                SeatAvailability(seat, seat not in booked)
                for seat in screening.room.seats()
            ]

    def _get_screening(self, screening_id: str) -> Screening:
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(
                f"unknown screening {screening_id!r}"
            ) from None
