import logging

logger = logging.getLogger(__name__)


class ProcessingException(Exception):
    """Generic failure raised at the boundary of the booking service."""


class SeatAlreadyBookedException(ProcessingException):
    """The requested seat is already booked for the screening."""


class UnknownSeatException(ProcessingException):
    """The requested seat or screening does not exist."""


class Room:
    """A room made of rows, each row holding a number of seats (1-based)."""

    def __init__(self, rows, seats_per_row):
        if rows < 1 or seats_per_row < 1:
            raise ValueError("a room needs at least one row and one seat")
        self.rows = rows
        self.seats_per_row = seats_per_row


class SeatBookingManager:
    """Registers screenings and books seats for clients."""

    def __init__(self):
        # screening id -> Room
        self._rooms = {}
        # screening id -> {(row, seat): client id}
        self._bookings = {}

    def add_screening(self, screening_id, room):
        if screening_id in self._rooms:
            raise ValueError("screening already exists: %s" % screening_id)
        self._rooms[screening_id] = room
        self._bookings[screening_id] = {}

    def _room_of(self, screening_id):
        try:
            return self._rooms[screening_id]
        except KeyError as error:
            logger.error("unknown screening %s", screening_id)
            raise UnknownSeatException("unknown screening: %s" % screening_id) from error

    def book_seat(self, screening_id, client_id, row, seat):
        room = self._room_of(screening_id)
        if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
            logger.error("unknown seat %s/%s in screening %s", row, seat, screening_id)
            raise UnknownSeatException("unknown seat: row %s, seat %s" % (row, seat))
        bookings = self._bookings[screening_id]
        if (row, seat) in bookings:
            logger.error("seat %s/%s already booked in screening %s", row, seat, screening_id)
            raise SeatAlreadyBookedException(
                "seat already booked: row %s, seat %s" % (row, seat))
        bookings[(row, seat)] = client_id

    def get_seat_availability(self, screening_id):
        """Return {(row, seat): True if free} for every seat of the screening."""
        room = self._room_of(screening_id)
        bookings = self._bookings[screening_id]
        return {
            (row, seat): (row, seat) not in bookings
            for row in range(1, room.rows + 1)
            for seat in range(1, room.seats_per_row + 1)
        }
