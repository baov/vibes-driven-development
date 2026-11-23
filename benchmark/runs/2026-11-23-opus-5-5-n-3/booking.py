"""Seat booking for cinema screenings.

A ``Room`` has rows of seats; a ``Screening`` takes place in a room; the
``BookingService`` lets clients book seats for a screening and reports the
availability of every seat.
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple


class BookingError(Exception):
    """Base class for booking failures."""


class UnknownScreeningError(BookingError):
    pass


class DuplicateScreeningError(BookingError):
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
    """A room with named rows; ``rows`` maps a row label to its seat count.

    Seats in a row are numbered from 1 to the seat count. Row order is the
    insertion order of ``rows``.
    """

    name: str
    rows: Mapping[str, int]

    def __post_init__(self):
        if not self.rows:
            raise ValueError("a room needs at least one row")
        for label, count in self.rows.items():
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                raise ValueError(f"row {label!r} must have a positive integer seat count")
        # Freeze a private copy so later changes to the caller's dict have no effect.
        object.__setattr__(self, "rows", dict(self.rows))

    def seats(self) -> List[Seat]:
        return [Seat(row, n) for row, count in self.rows.items() for n in range(1, count + 1)]

    def has_seat(self, seat: Seat) -> bool:
        count = self.rows.get(seat.row)
        return count is not None and 1 <= seat.number <= count


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    client_id: str
    seat: Seat


@dataclass
class BookingService:
    """In-memory booking service. Safe to use from several threads."""

    _screenings: Dict[str, Screening] = field(default_factory=dict)
    _bookings: Dict[Tuple[str, Seat], Booking] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_screening(self, screening: Screening) -> None:
        with self._lock:
            if screening.screening_id in self._screenings:
                raise DuplicateScreeningError(screening.screening_id)
            self._screenings[screening.screening_id] = screening

    def book(self, screening_id: str, client_id: str, row: str, number: int) -> Booking:
        """Book a seat. Raises ``SeatAlreadyBookedError`` if it is taken."""
        seat = Seat(row, number)
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(
                    f"seat {row}{number} does not exist in room {screening.room.name!r}"
                )
            key = (screening_id, seat)
            if key in self._bookings:
                raise SeatAlreadyBookedError(
                    f"seat {row}{number} is already booked for screening {screening_id!r}"
                )
            booking = Booking(screening_id, client_id, seat)
            self._bookings[key] = booking
            return booking

    def availability(self, screening_id: str) -> Dict[Seat, bool]:
        """Map every seat of the screening's room to True if it is still free.

        Seats are ordered row by row, then by seat number.
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            return {
                seat: (screening_id, seat) not in self._bookings
                for seat in screening.room.seats()
            }

    def _get_screening(self, screening_id: str) -> Screening:
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None
