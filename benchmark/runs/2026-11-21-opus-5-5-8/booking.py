"""Seat booking for cinema screenings.

A screening takes place in a room made of rows of seats. A client books one
seat of a screening at a time; a seat can be booked at most once per
screening. The manager also reports the availability of every seat.
"""

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class BookingError(Exception):
    """Base class for booking failures."""


class UnknownScreeningError(BookingError):
    """The requested screening does not exist."""


class DuplicateScreeningError(BookingError):
    """A screening with the same identifier is already registered."""


class UnknownSeatError(BookingError):
    """The requested seat does not exist in the screening's room."""


class SeatAlreadyBookedError(BookingError):
    """The requested seat is already booked for this screening."""


@dataclass(frozen=True)
class Room:
    """A room, described as an ordered mapping of row label -> seat count.

    Seats in a row are numbered from 1 to the row's seat count.
    """

    name: str
    rows: tuple  # tuple of (row_label: str, seat_count: int)

    def __post_init__(self):
        labels = [label for label, _ in self.rows]
        if len(set(labels)) != len(labels):
            raise ValueError(f"duplicate row labels in room {self.name!r}")
        for label, seat_count in self.rows:
            if seat_count < 1:
                raise ValueError(f"row {label!r} must have at least one seat")

    def seats(self):
        """All seats of the room as (row_label, seat_number), in room order."""
        return [
            (label, number)
            for label, seat_count in self.rows
            for number in range(1, seat_count + 1)
        ]

    def has_seat(self, row, number):
        return any(label == row and 1 <= number <= count for label, count in self.rows)


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


class BookingManager:
    """Registers screenings, books seats and reports seat availability.

    State is held in memory. All operations are serialized by a lock so that
    two concurrent bookings of the same seat cannot both succeed.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._screenings = {}
        # screening_id -> {(row, number): client_id}
        self._bookings = {}

    def add_screening(self, screening):
        with self._lock:
            if screening.screening_id in self._screenings:
                raise DuplicateScreeningError(screening.screening_id)
            self._screenings[screening.screening_id] = screening
            self._bookings[screening.screening_id] = {}

    def book_seat(self, screening_id, row, number, client_id):
        """Book seat (row, number) of a screening for a client.

        Raises UnknownScreeningError, UnknownSeatError or
        SeatAlreadyBookedError; on any of these, nothing is booked.
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(row, number):
                raise UnknownSeatError(f"{screening_id}: no seat {row}{number}")
            bookings = self._bookings[screening_id]
            if (row, number) in bookings:
                logger.info("rejected booking of %s%s for %s: already booked",
                            row, number, screening_id)
                raise SeatAlreadyBookedError(f"{screening_id}: seat {row}{number} already booked")
            bookings[(row, number)] = client_id

    def seat_availability(self, screening_id):
        """Return {(row, number): is_available} for every seat of the screening."""
        with self._lock:
            screening = self._get_screening(screening_id)
            bookings = self._bookings[screening_id]
            return {seat: seat not in bookings for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None
