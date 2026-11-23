"""Seat booking for cinema screenings."""

from dataclasses import dataclass
from threading import Lock


class BookingError(Exception):
    """Base class for booking failures."""


class UnknownScreeningError(BookingError):
    pass


class DuplicateScreeningError(BookingError):
    pass


class InvalidSeatError(BookingError):
    pass


class SeatAlreadyBookedError(BookingError):
    pass


@dataclass(frozen=True)
class Seat:
    """A seat position. Rows and seat numbers both start at 1."""

    row: int
    number: int


@dataclass(frozen=True)
class Room:
    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def seats(self):
        """All seats of the room, ordered by row then seat number."""
        return [
            Seat(row, number)
            for row in range(1, self.rows + 1)
            for number in range(1, self.seats_per_row + 1)
        ]

    def has_seat(self, seat):
        return 1 <= seat.row <= self.rows and 1 <= seat.number <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    id: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    seat: Seat
    client: str


class BookingService:
    """In-memory booking service. Safe to use from several threads."""

    def __init__(self):
        self._screenings = {}
        # screening id -> {Seat: Booking}
        self._bookings = {}
        self._lock = Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise DuplicateScreeningError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def book_seat(self, screening_id, row, number, client):
        """Book a seat for a client. Rejects seats that are already booked."""
        seat = Seat(row, number)
        with self._lock:
            screening = self._get_screening(screening_id)
            if not screening.room.has_seat(seat):
                raise InvalidSeatError(
                    f"row {row}, seat {number} does not exist in room {screening.room.name!r}"
                )
            bookings = self._bookings[screening_id]
            if seat in bookings:
                raise SeatAlreadyBookedError(
                    f"row {row}, seat {number} is already booked for screening {screening_id!r}"
                )
            booking = Booking(screening_id, seat, client)
            bookings[seat] = booking
            return booking

    def seat_availability(self, screening_id):
        """Map every seat of the screening's room to True if free, False if booked.

        Seats are ordered by row then seat number.
        """
        with self._lock:
            screening = self._get_screening(screening_id)
            booked = self._bookings[screening_id]
            return {seat: seat not in booked for seat in screening.room.seats()}

    def _get_screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(f"unknown screening {screening_id!r}") from None
