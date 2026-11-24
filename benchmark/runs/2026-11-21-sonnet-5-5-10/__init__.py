# Import the dataclass decorator so entities stay plain data structures
from dataclasses import dataclass, field
# Import logging so every exception is logged at the layer it passes through
import logging
# Import threading so check-then-book is atomic and a seat cannot be double booked
import threading

# Module logger used by the manager to record every failure
logger = logging.getLogger(__name__)


# Generic exception exposed at the boundary of the manager
class ProcessingException(Exception):
    # Marker class only, the message carries the reason
    pass


# Specific rejection so callers can tell "already booked" from other failures
class SeatAlreadyBookedException(ProcessingException):
    # Marker class only, the message carries the reason
    pass


# Room is plain data: a rectangular grid of rows x seats_per_row (1-based numbering)
@dataclass
class Room:
    # Identifier of the room
    room_id: str
    # Number of rows in the room
    rows: int
    # Number of seats in each row
    seats_per_row: int


# Screening is plain data: a showing that takes place in one room
@dataclass
class Screening:
    # Identifier of the screening
    screening_id: str
    # Room where the screening takes place
    room: Room
    # Bookings of this screening, keyed by (row, seat) with the client id as value
    bookings: dict = field(default_factory=dict)


# Manager holding the booking rules (behavior lives in the manager, entities are data)
class SeatBookingManager:
    # Build an empty manager
    def __init__(self):
        # Screenings known to the manager, keyed by screening id
        self.screenings = {}
        # Lock protecting the check-then-book sequence
        self.lock = threading.Lock()

    # Register a screening so it can receive bookings
    def add_screening(self, screening):
        # Store the screening under its id
        self.screenings[screening.screening_id] = screening
        # Return the stored screening for convenience
        return screening

    # Book one seat of one screening for a client; reject it when already booked
    def book_seat(self, screening_id, row, seat, client_id):
        # Log and rethrow every failure
        try:
            # Make the check and the booking one atomic step
            with self.lock:
                # Fetch the screening (KeyError when unknown)
                screening = self.screenings[screening_id]
                # Reject seats that are not in the room
                if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
                    # Signal the invalid seat
                    raise ProcessingException("Seat (%s, %s) does not exist in screening %s" % (row, seat, screening_id))
                # Reject seats that are already booked
                if (row, seat) in screening.bookings:
                    # Signal the double booking
                    raise SeatAlreadyBookedException("Seat (%s, %s) is already booked for screening %s" % (row, seat, screening_id))
                # Record the booking
                screening.bookings[(row, seat)] = client_id
            # Return the booked seat as (row, seat)
            return (row, seat)
        # Unknown screening id
        except KeyError as exc:
            # Log the failure with its traceback
            logger.exception("book_seat failed: unknown screening %s", screening_id)
            # Wrap in the generic exception at the layer boundary
            raise ProcessingException("Unknown screening %s" % screening_id) from exc
        # Exceptions already shaped by this layer
        except ProcessingException:
            # Log the failure with its traceback
            logger.exception("book_seat failed")
            # Rethrow unchanged so callers keep the specific type
            raise

    # Expose the availability of every seat of a screening
    def get_seat_availability(self, screening_id):
        # Log and rethrow every failure
        try:
            # Fetch the screening (KeyError when unknown)
            screening = self.screenings[screening_id]
            # Snapshot the availability under the lock so it is consistent
            with self.lock:
                # True means available, False means booked, for every (row, seat) of the room
                return {
                    (row, seat): (row, seat) not in screening.bookings
                    for row in range(1, screening.room.rows + 1)
                    for seat in range(1, screening.room.seats_per_row + 1)
                }
        # Unknown screening id
        except KeyError as exc:
            # Log the failure with its traceback
            logger.exception("get_seat_availability failed: unknown screening %s", screening_id)
            # Wrap in the generic exception at the layer boundary
            raise ProcessingException("Unknown screening %s" % screening_id) from exc
