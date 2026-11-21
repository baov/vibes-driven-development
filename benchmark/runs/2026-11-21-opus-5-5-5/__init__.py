"""Seat reservation service for a cinema chain."""

# Standard library logging, so every rejection is observable.
import logging
# Lock guarding the check-then-book sequence against concurrent double booking.
import threading

# Module-level logger for the seat booking service.
logger = logging.getLogger(__name__)


# Base error raised by the seat booking service.
class ProcessingException(Exception):
    pass


# Raised when a screening id is unknown.
class ScreeningNotFoundException(ProcessingException):
    pass


# Raised when a screening id is registered twice.
class ScreeningAlreadyExistsException(ProcessingException):
    pass


# Raised when the requested row or seat does not exist in the screening's room.
class SeatNotFoundException(ProcessingException):
    pass


# Raised when the requested seat is already booked for the screening.
class SeatAlreadyBookedException(ProcessingException):
    pass


class SeatBookingManager:
    """Registers screenings, books seats and reports seat availability.

    A room is described by its rows: a mapping from row label to the number of
    seats in that row (seats are numbered from 1). Each screening takes place in
    one room and keeps its own bookings, keyed by (row, seat).
    """

    def __init__(self):
        # screening id -> {"rows": {row label: seat count}, "bookings": {(row, seat): client id}}
        self._screenings = {}
        # Serializes every read and write of the screenings and their bookings.
        self._lock = threading.Lock()

    def add_screening(self, screening_id, rows):
        # Reject rooms without rows or with a row that has no seats.
        if not rows or any(count < 1 for count in rows.values()):
            # Log the invalid room before raising.
            logger.warning("Invalid room for screening %s: %r", screening_id, rows)
            # Signal the invalid room to the caller.
            raise ValueError("a room needs at least one row and every row at least one seat")
        # Hold the lock while checking and registering the screening.
        with self._lock:
            # Refuse to silently overwrite an existing screening and its bookings.
            if screening_id in self._screenings:
                # Log the duplicate registration before raising.
                logger.warning("Screening %s already exists", screening_id)
                # Signal the duplicate to the caller.
                raise ScreeningAlreadyExistsException(screening_id)
            # Copy the room layout so later changes by the caller have no effect, and start with no bookings.
            self._screenings[screening_id] = {"rows": dict(rows), "bookings": {}}

    def book_seat(self, screening_id, row, seat, client_id):
        # Hold the lock so two clients cannot both pass the availability check for the same seat.
        with self._lock:
            # Look up the screening.
            screening = self._screenings.get(screening_id)
            # Reject unknown screenings.
            if screening is None:
                # Log the unknown screening before raising.
                logger.warning("Booking rejected: unknown screening %s", screening_id)
                # Signal the unknown screening to the caller.
                raise ScreeningNotFoundException(screening_id)
            # Reject rows that are not in the room and seat numbers outside the row.
            if row not in screening["rows"] or not 1 <= seat <= screening["rows"][row]:
                # Log the invalid seat before raising.
                logger.warning("Booking rejected: no seat %s%s in screening %s", row, seat, screening_id)
                # Signal the invalid seat to the caller.
                raise SeatNotFoundException(f"{row}{seat}")
            # Reject a seat that is already booked for this screening.
            if (row, seat) in screening["bookings"]:
                # Log the double booking attempt before raising.
                logger.warning("Booking rejected: seat %s%s already booked in screening %s", row, seat, screening_id)
                # Signal the double booking to the caller.
                raise SeatAlreadyBookedException(f"{row}{seat}")
            # Record the booking for this client.
            screening["bookings"][(row, seat)] = client_id

    def get_seat_availability(self, screening_id):
        # Hold the lock so the snapshot is consistent with concurrent bookings.
        with self._lock:
            # Look up the screening.
            screening = self._screenings.get(screening_id)
            # Reject unknown screenings.
            if screening is None:
                # Log the unknown screening before raising.
                logger.warning("Availability rejected: unknown screening %s", screening_id)
                # Signal the unknown screening to the caller.
                raise ScreeningNotFoundException(screening_id)
            # One entry per seat of the room, in row order then seat order.
            return [
                {"row": row, "seat": seat, "available": (row, seat) not in screening["bookings"]}
                for row, count in screening["rows"].items()
                for seat in range(1, count + 1)
            ]
