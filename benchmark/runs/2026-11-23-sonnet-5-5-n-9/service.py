"""Seat booking: rooms, screenings and the booking service."""
from dataclasses import dataclass
from threading import Lock


class SeatAlreadyBookedError(Exception):
    """Raised when booking a seat that is already booked for a screening."""


class UnknownSeatError(ValueError):
    """Raised when a seat does not exist in the screening's room."""


class UnknownScreeningError(KeyError):
    """Raised when a screening id is not registered."""


@dataclass(frozen=True)
class Seat:
    row: int
    number: int


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows, each holding `seats_per_row` seats (1-based)."""
    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def seats(self):
        return [Seat(r, n) for r in range(1, self.rows + 1)
                for n in range(1, self.seats_per_row + 1)]

    def has_seat(self, seat):
        return 1 <= seat.row <= self.rows and 1 <= seat.number <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    id: str
    film: str
    room: Room


class BookingService:
    def __init__(self):
        self._screenings = {}
        self._bookings = {}  # screening id -> {Seat: client}
        self._lock = Lock()

    def add_screening(self, screening):
        with self._lock:
            if screening.id in self._screenings:
                raise ValueError(f"screening {screening.id!r} already exists")
            self._screenings[screening.id] = screening
            self._bookings[screening.id] = {}

    def _screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None

    def book(self, screening_id, client, seat):
        """Book `seat` for `client`; rejects a seat that is already booked."""
        with self._lock:
            screening = self._screening(screening_id)
            if not screening.room.has_seat(seat):
                raise UnknownSeatError(seat)
            booked = self._bookings[screening_id]
            if seat in booked:
                raise SeatAlreadyBookedError(seat)
            booked[seat] = client

    def availability(self, screening_id):
        """Return {Seat: True if available} for every seat of the screening."""
        with self._lock:
            screening = self._screening(screening_id)
            booked = self._bookings[screening_id]
            return {s: s not in booked for s in screening.room.seats()}
