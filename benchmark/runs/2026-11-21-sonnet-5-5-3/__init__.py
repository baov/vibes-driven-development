# Import threading to guard the check-then-book sequence against concurrent clients.
import threading
# Import logging to record every exception before it is rethrown.
import logging
# Import dataclass to declare plain data structures.
from dataclasses import dataclass

# Module logger used by every layer in this file.
logger = logging.getLogger(__name__)


# Generic exception exposed at the boundary of the booking layer.
class ProcessingException(Exception):
    # No extra behavior is needed for the generic exception.
    pass


# Specific rejection raised when a seat is already booked for a screening.
class SeatAlreadyBookedException(ProcessingException):
    # No extra behavior is needed for this rejection.
    pass


# Plain data: a room made of rows, each row holding the same number of seats.
@dataclass
class Room:
    # Human readable name of the room.
    name: str
    # Number of rows in the room (rows are numbered from 1).
    row_count: int
    # Number of seats in each row (seats are numbered from 1).
    seats_per_row: int


# Plain data: a screening takes place in one room.
@dataclass
class Screening:
    # Identifier of the screening.
    screening_id: str
    # Room where the screening takes place.
    room: Room


# Manager holding the booking rules for every screening.
class SeatBookingManager:
    # Create an empty manager.
    def __init__(self):
        # Known screenings, keyed by screening id.
        self._screenings = {}
        # Bookings, keyed by (screening id, row, seat) and valued by client id.
        self._bookings = {}
        # Lock making the availability check and the booking one atomic step.
        self._lock = threading.Lock()

    # Make a screening known to the manager.
    def register_screening(self, screening):
        # Store the screening under its id.
        self._screenings[screening.screening_id] = screening

    # Book one seat of a screening for a client; reject it if already booked.
    def book_seat(self, screening_id, row, seat, client_id):
        # Log and rethrow every processing failure.
        try:
            # Look up the screening, None when unknown.
            info = self._screenings.get(screening_id)
            # Reject an unknown screening.
            if info is None:
                # Raise the generic exception with a clear message.
                raise ProcessingException("Unknown screening: %s" % screening_id)
            # Reject a seat outside the room.
            if not (1 <= row <= info.room.row_count and 1 <= seat <= info.room.seats_per_row):
                # Raise the generic exception with a clear message.
                raise ProcessingException("Seat does not exist: row %s seat %s" % (row, seat))
            # Key identifying this seat for this screening.
            data = (screening_id, row, seat)
            # Hold the lock so two clients cannot book the same seat.
            with self._lock:
                # Reject a seat that is already booked.
                if data in self._bookings:
                    # Raise the specific rejection.
                    raise SeatAlreadyBookedException(
                        "Seat already booked: row %s seat %s" % (row, seat))
                # Record the booking for the client.
                self._bookings[data] = client_id
        # Catch the failure to log it at this layer.
        except ProcessingException as error:
            # Log the failure.
            logger.error("book_seat failed: %s", error)
            # Rethrow the same exception.
            raise

    # Expose the availability of every seat of a screening.
    def get_seat_availability(self, screening_id):
        # Log and rethrow every processing failure.
        try:
            # Look up the screening, None when unknown.
            info = self._screenings.get(screening_id)
            # Reject an unknown screening.
            if info is None:
                # Raise the generic exception with a clear message.
                raise ProcessingException("Unknown screening: %s" % screening_id)
            # Seats listed in row then seat order.
            result = []
            # Walk every row of the room.
            for row in range(1, info.room.row_count + 1):
                # Walk every seat of the row.
                for seat in range(1, info.room.seats_per_row + 1):
                    # A seat is available when no booking exists for it.
                    available = (screening_id, row, seat) not in self._bookings
                    # Add the seat and its availability to the listing.
                    result.append({"row": row, "seat": seat, "available": available})
            # Return the full listing.
            return result
        # Catch the failure to log it at this layer.
        except ProcessingException as error:
            # Log the failure.
            logger.error("get_seat_availability failed: %s", error)
            # Rethrow the same exception.
            raise
