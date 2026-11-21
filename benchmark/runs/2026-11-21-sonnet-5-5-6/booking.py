"""Seat booking: rooms, screenings, bookings and seat availability."""

from dataclasses import dataclass


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
    row: int
    number: int


@dataclass(frozen=True)
class Room:
    """A room with `rows` rows of `seats_per_row` seats (1-indexed)."""

    name: str
    rows: int
    seats_per_row: int

    def __post_init__(self):
        if self.rows < 1 or self.seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")

    def seats(self):
        return [
            Seat(r, n)
            for r in range(1, self.rows + 1)
            for n in range(1, self.seats_per_row + 1)
        ]

    def has_seat(self, seat):
        return 1 <= seat.row <= self.rows and 1 <= seat.number <= self.seats_per_row


@dataclass(frozen=True)
class Screening:
    id: str
    film: str
    room: Room


@dataclass(frozen=True)
class Booking:
    screening_id: str
    seat: Seat
    client: str


class BookingService:
    """In-memory booking service. Not thread-safe."""

    def __init__(self):
        self._screenings = {}
        self._bookings = {}  # (screening_id, Seat) -> Booking

    def add_screening(self, screening):
        if screening.id in self._screenings:
            raise ValueError(f"screening {screening.id!r} already exists")
        self._screenings[screening.id] = screening

    def _screening(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None

    def book(self, screening_id, seat, client):
        """Book `seat` for `client`; reject unknown seats and double bookings."""
        screening = self._screening(screening_id)
        if not screening.room.has_seat(seat):
            raise UnknownSeatError(seat)
        key = (screening_id, seat)
        if key in self._bookings:
            raise SeatAlreadyBookedError(seat)
        booking = Booking(screening_id, seat, client)
        self._bookings[key] = booking
        return booking

    def availability(self, screening_id):
        """Return {Seat: bool} for every seat of the screening (True = free)."""
        screening = self._screening(screening_id)
        return {s: (screening_id, s) not in self._bookings for s in screening.room.seats()}
