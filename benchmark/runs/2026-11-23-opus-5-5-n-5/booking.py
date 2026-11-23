"""Seat booking for cinema screenings.

A Room has rows of seats; a Screening takes place in a Room. The
BookingManager registers screenings, books seats for clients, and reports
the availability of every seat of a screening.
"""

import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for all booking failures."""


class UnknownScreeningError(BookingError):
    """The screening id is not registered."""


class InvalidSeatError(BookingError):
    """The requested row/seat does not exist in the screening's room."""


class SeatAlreadyBookedError(BookingError):
    """The seat is already booked for this screening."""


@dataclass(frozen=True)
class Room:
    """A room whose rows are numbered from 1; seats_per_row[i] is the size of row i+1."""

    name: str
    seats_per_row: tuple

    def __post_init__(self):
        # Normalise to a tuple so the room stays immutable even if a list was passed.
        object.__setattr__(self, "seats_per_row", tuple(self.seats_per_row))
        # A room without rows, or with an empty row, cannot host a screening.
        if not self.seats_per_row or any(
            not isinstance(n, int) or n < 1 for n in self.seats_per_row
        ):
            raise ValueError("a room needs at least one row, each with at least one seat")

    @classmethod
    def rectangular(cls, name, rows, seats_per_row):
        """Build a room where every row has the same number of seats."""
        return cls(name, (seats_per_row,) * rows)

    def has_seat(self, row, seat):
        """Return True when (row, seat) exists in this room (both 1-based)."""
        return (
            isinstance(row, int)
            and isinstance(seat, int)
            and 1 <= row <= len(self.seats_per_row)
            and 1 <= seat <= self.seats_per_row[row - 1]
        )

    def seats(self):
        """Yield every (row, seat) of the room in row-major order."""
        for row, count in enumerate(self.seats_per_row, start=1):
            for seat in range(1, count + 1):
                yield (row, seat)


@dataclass(frozen=True)
class Screening:
    screening_id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    row: int
    seat: int
    client_id: str


class BookingManager:
    """In-memory, thread-safe booking service."""

    def __init__(self):
        # Registered screenings, keyed by screening id.
        self._screenings = {}
        # Bookings per screening: {screening_id: {(row, seat): Booking}}.
        self._bookings = {}
        # Guards check-then-book so two clients cannot book the same seat.
        self._lock = threading.Lock()

    def add_screening(self, screening):
        """Register a screening; its id must be unique."""
        with self._lock:
            # Re-registering an id would silently drop or mix existing bookings.
            if screening.screening_id in self._screenings:
                raise ValueError(f"screening {screening.screening_id!r} already exists")
            self._screenings[screening.screening_id] = screening
            self._bookings[screening.screening_id] = {}

    def book(self, screening_id, row, seat, client_id):
        """Book (row, seat) of a screening for a client and return the Booking.

        Raises UnknownScreeningError, InvalidSeatError or SeatAlreadyBookedError.
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            # Reject seats that do not exist in the room.
            if not screening.room.has_seat(row, seat):
                raise InvalidSeatError(
                    f"row {row} seat {seat} does not exist in room {screening.room.name!r}"
                )
            bookings = self._bookings[screening_id]
            # A seat can be booked only once per screening.
            if (row, seat) in bookings:
                raise SeatAlreadyBookedError(
                    f"row {row} seat {seat} is already booked for screening {screening_id!r}"
                )
            booking = Booking(screening_id, row, seat, client_id)
            bookings[(row, seat)] = booking
            return booking

    def availability(self, screening_id):
        """Return {(row, seat): is_available} for every seat of the screening."""
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {
                position: position not in booked
                for position in screening.room.seats()
            }

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
