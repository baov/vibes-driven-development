"""Seat booking: rooms made of rows and seats, screenings, and client bookings."""


class BookingError(Exception):
    """Base class for booking failures."""


class SeatAlreadyBookedError(BookingError):
    pass


class UnknownSeatError(BookingError):
    pass


class UnknownScreeningError(BookingError):
    pass


class Room:
    def __init__(self, name, rows, seats_per_row):
        if rows < 1 or seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat per row")
        self.name = name
        self.rows = rows
        self.seats_per_row = seats_per_row

    def seats(self):
        """All seats as (row, seat) pairs, 1-based, in row order."""
        return [(r, s) for r in range(1, self.rows + 1)
                for s in range(1, self.seats_per_row + 1)]

    def has_seat(self, row, seat):
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


class Screening:
    def __init__(self, screening_id, room, title, starts_at=None):
        self.id = screening_id
        self.room = room
        self.title = title
        self.starts_at = starts_at
        # (row, seat) -> client
        self.bookings = {}


class BookingService:
    def __init__(self):
        self._screenings = {}

    def add_screening(self, screening):
        self._screenings[screening.id] = screening

    def _get(self, screening_id):
        try:
            return self._screenings[screening_id]
        except KeyError:
            raise UnknownScreeningError(screening_id) from None

    def book_seat(self, screening_id, client, row, seat):
        screening = self._get(screening_id)
        if not screening.room.has_seat(row, seat):
            raise UnknownSeatError((row, seat))
        if (row, seat) in screening.bookings:
            raise SeatAlreadyBookedError((row, seat))
        screening.bookings[(row, seat)] = client

    def availability(self, screening_id):
        """Map every seat (row, seat) of the screening to True if still free."""
        screening = self._get(screening_id)
        return {s: s not in screening.bookings for s in screening.room.seats()}
