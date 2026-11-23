"""Seat booking for cinema screenings."""

import threading
from dataclasses import dataclass, field
from typing import Dict, Mapping, Tuple


class BookingError(Exception):
    """Base class for booking failures."""


class UnknownScreeningError(BookingError):
    pass


class UnknownSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


SeatKey = Tuple[str, int]


@dataclass(frozen=True)
class Room:
    """A room with named rows; each row has seats numbered 1..n."""

    name: str
    rows: Mapping[str, int]

    def __post_init__(self):
        if not self.rows:
            raise ValueError("a room needs at least one row")
        for row, count in self.rows.items():
            if count < 1:
                raise ValueError(f"row {row!r} must have at least one seat")
        # Freeze a private copy so later changes to the caller's dict
        # cannot alter the room's layout.
        object.__setattr__(self, "rows", dict(self.rows))

    def has_seat(self, row: str, seat: int) -> bool:
        return row in self.rows and 1 <= seat <= self.rows[row]

    def seats(self):
        for row, count in self.rows.items():
            for seat in range(1, count + 1):
                yield (row, seat)


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


@dataclass
class BookingService:
    """In-memory booking service. Safe to use from several threads."""

    _screenings: Dict[str, Screening] = field(default_factory=dict)
    _bookings: Dict[str, Dict[SeatKey, Booking]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_screening(self, screening: Screening) -> None:
        with self._lock:
            if screening.screening_id in self._screenings:
                raise ValueError(
                    f"screening {screening.screening_id!r} already exists"
                )
            self._screenings[screening.screening_id] = screening
            self._bookings[screening.screening_id] = {}

    def book_seat(
        self, screening_id: str, row: str, seat: int, client_id: str
    ) -> Booking:
        """Book a seat, or raise if it does not exist or is already booked."""
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(row, seat):
                raise UnknownSeatError(
                    f"seat {row}{seat} does not exist in room "
                    f"{screening.room.name!r}"
                )
            bookings = self._bookings[screening_id]
            if (row, seat) in bookings:
                raise SeatAlreadyBookedError(
                    f"seat {row}{seat} is already booked for screening "
                    f"{screening_id!r}"
                )
            booking = Booking(screening_id, row, seat, client_id)
            bookings[(row, seat)] = booking
            return booking

    def availability(self, screening_id: str) -> Dict[SeatKey, bool]:
        """Map every seat of the screening's room to True if it is free."""
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {key: key not in booked for key in screening.room.seats()}

    def _get_screening(self, screening_id: str) -> Screening:
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(
                f"unknown screening {screening_id!r}"
            ) from None
