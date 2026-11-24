"""Seat booking for cinema screenings."""

import threading
from dataclasses import dataclass


class BookingError(Exception):
    """Base class for booking failures."""


class SeatAlreadyBookedError(BookingError):
    """Raised when a seat is already booked for the screening."""


class UnknownSeatError(BookingError):
    """Raised when a seat does not exist in the screening's room."""


class UnknownScreeningError(BookingError):
    """Raised when a screening id is not registered with the service."""


@dataclass(frozen=True)
class Seat:
    """A seat identified by its row label and its number within the row."""

    row: str
    number: int


@dataclass(frozen=True)
class Room:
    """A room whose rows map a row label to the number of seats in that row."""

    name: str
    rows: dict

    def seats(self):
        """Return every seat of the room, row by row, in seat-number order."""
        return [
            Seat(row, number)
            for row, seat_count in self.rows.items()
            for number in range(1, seat_count + 1)
        ]

    def has_seat(self, seat):
        """Return True if the seat exists in this room."""
        return 1 <= seat.number <= self.rows.get(seat.row, 0)


@dataclass(frozen=True)
class Screening:
    """A showing of a film in a room."""

    screening_id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    """A confirmed booking of one seat for one screening by one client."""

    screening_id: str
    seat: Seat
    client_id: str


class BookingService:
    """In-memory, thread-safe seat booking service."""

    def __init__(self):
        self._screenings = {}
        # screening_id -> {Seat: Booking}
        self._bookings = {}
        # Check-then-insert in book_seat must be atomic to prevent double booking.
        self._lock = threading.Lock()

    def add_screening(self, screening):
        """Register a screening so that its seats can be booked."""
        with self._lock:
            self._screenings[screening.screening_id] = screening
            self._bookings.setdefault(screening.screening_id, {})

    def book_seat(self, screening_id, seat, client_id):
        """Book a seat for a client; reject seats that are unknown or already booked."""
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(
                    f"Seat {seat.row}{seat.number} does not exist in room {screening.room.name}"
                )
            bookings = self._bookings[screening_id]
            if seat in bookings:
                raise SeatAlreadyBookedError(
                    f"Seat {seat.row}{seat.number} is already booked for screening {screening_id}"
                )
            booking = Booking(screening_id, seat, client_id)
            bookings[seat] = booking
            return booking

    def seat_availability(self, screening_id):
        """Return {Seat: bool} for every seat of the screening; True means available."""
        with self._lock:
            screening = self._get_screening(screening_id)
            bookings = self._bookings[screening_id]
            return {seat: seat not in bookings for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"Unknown screening {screening_id}") from None
