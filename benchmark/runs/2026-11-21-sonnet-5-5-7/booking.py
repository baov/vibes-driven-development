"""Seat booking: rooms, screenings and bookings, kept in one module (locality of behavior)."""

import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for booking rejections."""


class SeatAlreadyBookedError(BookingError):
    """The requested seat is already booked for this screening."""


class UnknownSeatError(BookingError):
    """The requested seat does not exist in the screening's room."""


class UnknownScreeningError(BookingError):
    """The screening is not registered."""


@dataclass(frozen=True)
class Room:
    """A room made of `rows` rows of `seats_per_row` seats (1-based numbering)."""

    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def has_seat(self, row, seat):
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    """A film shown in a room; identified by `screening_id`."""

    screening_id: str
    title: str
    room: Room


class BookingManager:
    """Registers screenings, books seats and reports seat availability."""

    def __init__(self):
        self._screenings = {}
        # (screening_id, row, seat) -> client_id
        self._bookings = {}
        # Guards check-then-set in book_seat so two clients cannot both win a seat.
        self._lock = threading.Lock()

    def add_screening(self, screening):
        self._screenings[screening.screening_id] = screening

    def book_seat(self, screening_id, client_id, row, seat):
        """Book a seat for a client; raises BookingError subclasses on rejection."""
        screening = self._get_screening(screening_id)
        if not screening.room.has_seat(row, seat):
            raise UnknownSeatError(f"seat {row}/{seat} does not exist in room {screening.room.name}")
        key = (screening_id, row, seat)
        with self._lock:
            if key in self._bookings:
                raise SeatAlreadyBookedError(f"seat {row}/{seat} is already booked for {screening_id}")
            self._bookings[key] = client_id

    def seat_availability(self, screening_id):
        """Return {(row, seat): True if available} for every seat of the screening."""
        screening = self._get_screening(screening_id)
        room = screening.room
        with self._lock:
            return {
                (row, seat): (screening_id, row, seat) not in self._bookings
                for row in range(1, room.rows + 1)
                for seat in range(1, room.seats_per_row + 1)
            }

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id}") from None
