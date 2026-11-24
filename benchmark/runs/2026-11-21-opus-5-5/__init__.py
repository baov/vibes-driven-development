"""Seat booking for cinema screenings.

A screening takes place in a room made of rows of seats. A client books one
seat of one screening; a seat can be booked by at most one client per
screening.
"""

import threading
from dataclasses import dataclass, field


class BookingError(Exception):
    """Base class for every booking rejection."""


class UnknownScreeningError(BookingError):
    """The screening id is not known to the service."""


class UnknownSeatError(BookingError):
    """The row or seat number does not exist in the screening's room."""


class SeatAlreadyBookedError(BookingError):
    """The seat is already booked for this screening."""


@dataclass(frozen=True)
class Room:
    """A room: each row label maps to its number of seats, numbered from 1."""

    name: str
    rows: dict

    def __post_init__(self):
        # A room without rows, or a row without seats, cannot host a screening.
        if not self.rows:
            raise ValueError("a room needs at least one row")
        for row, seat_count in self.rows.items():
            if not isinstance(seat_count, int) or seat_count < 1:
                raise ValueError(f"row {row!r} needs a positive seat count")

    def has_seat(self, row, seat):
        # Seats are numbered 1..seat_count within their row.
        return row in self.rows and 1 <= seat <= self.rows[row]


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


@dataclass
class _ScreeningBookings:
    screening: Screening
    # (row, seat) -> client_id
    booked: dict = field(default_factory=dict)


class BookingManager:
    """In-memory booking service. Safe to call from several threads."""

    def __init__(self):
        self._screenings = {}
        self._lock = threading.Lock()

    def add_screening(self, screening):
        with self._lock:
            # Re-adding a screening would silently drop its existing bookings.
            if screening.screening_id in self._screenings:
                raise ValueError(f"screening {screening.screening_id!r} already exists")
            self._screenings[screening.screening_id] = _ScreeningBookings(screening)

    def book_seat(self, screening_id, row, seat, client_id):
        """Book (row, seat) of the screening for the client.

        Raises UnknownScreeningError, UnknownSeatError or SeatAlreadyBookedError.
        The check and the booking happen under one lock, so two concurrent
        requests for the same seat cannot both succeed.
        """
        with self._lock:
            bookings = self._get(screening_id)
            if not bookings.screening.room.has_seat(row, seat):
                raise UnknownSeatError(
                    f"seat {row}{seat} does not exist in room {bookings.screening.room.name!r}"
                )
            if (row, seat) in bookings.booked:
                raise SeatAlreadyBookedError(
                    f"seat {row}{seat} is already booked for screening {screening_id!r}"
                )
            bookings.booked[(row, seat)] = client_id

    def seat_availability(self, screening_id):
        """Return {(row, seat): True if available, False if booked} for every seat."""
        with self._lock:
            bookings = self._get(screening_id)
            return {
                (row, seat): (row, seat) not in bookings.booked
                for row, seat_count in bookings.screening.room.rows.items()
                for seat in range(1, seat_count + 1)
            }

    def _get(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
