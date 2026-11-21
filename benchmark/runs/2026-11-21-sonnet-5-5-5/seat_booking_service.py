# Module for the seat booking feature: data structures and the service holding the rules.
# Everything lives in one file to keep the behavior local (file is far below 1,250 lines).

# Standard library logging, used to log every exception before it is rethrown.
import logging
# Lock used to make "check then book" atomic between concurrent clients.
import threading
# Dataclasses give plain data structures (fields only).
from dataclasses import dataclass

# Module level logger.
logger = logging.getLogger(__name__)


# Generic failure type raised at the service boundary.
class ProcessingException(Exception):
    pass


# Raised when a seat is booked twice for the same screening; specific so callers can react.
class SeatAlreadyBookedException(ProcessingException):
    pass


# A room is a plain grid: a number of rows, each with the same number of seats.
@dataclass
class Room:
    # Number of rows in the room (rows are numbered from 1).
    rows: int
    # Number of seats in each row (seats are numbered from 1).
    seats_per_row: int


# A screening takes place in a room.
@dataclass
class Screening:
    # Identifier of the screening.
    id: str
    # Room where the screening takes place.
    room: Room


# A client's booking of one seat for one screening.
@dataclass
class Booking:
    # Screening the seat is booked for.
    screening_id: str
    # Client who booked the seat.
    client_id: str
    # Row of the seat.
    row: int
    # Seat number inside the row.
    seat: int


# Service holding the business rules of seat booking.
class SeatBookingService:
    # Start with no screening and no booking.
    def __init__(self):
        # Screenings by identifier.
        self.screenings = {}
        # Bookings by (screening id, row, seat); the key guarantees one booking per seat.
        self.bookings = {}
        # Protects the bookings against concurrent access.
        self.lock = threading.Lock()

    # Make a screening known to the service.
    def register_screening(self, screening):
        # Store the screening under its identifier.
        self.screenings[screening.id] = screening

    # Book a seat for a client; rejects unknown screenings, unknown seats and booked seats.
    def book_seat(self, screening_id, client_id, row, seat):
        try:
            # Only one booking at a time may check and take a seat.
            with self.lock:
                # Fail if the screening is unknown.
                screening = self._get_screening(screening_id)
                # Fail if the seat does not exist in the room.
                self._check_seat_exists(screening, row, seat)
                # Key identifying this exact seat for this exact screening.
                key = (screening_id, row, seat)
                # Reject a seat that is already booked.
                if key in self.bookings:
                    raise SeatAlreadyBookedException(
                        "Seat %d of row %d is already booked for screening %s" % (seat, row, screening_id))
                # Record the booking.
                result = Booking(screening_id, client_id, row, seat)
                # Store it so the seat becomes unavailable.
                self.bookings[key] = result
                # Hand the booking back to the caller.
                return result
        except ProcessingException:
            # Log the exception at this layer.
            logger.exception("Booking failed")
            # Rethrow it unchanged (it already is a ProcessingException).
            raise

    # Availability of every seat of a screening: {(row, seat): True when free}.
    def get_seat_availability(self, screening_id):
        try:
            # Read under the lock to see a consistent state.
            with self.lock:
                # Fail if the screening is unknown.
                screening = self._get_screening(screening_id)
                # Every seat of the room, free unless a booking exists for it.
                result = {}
                # Walk the rows of the room.
                for row in range(1, screening.room.rows + 1):
                    # Walk the seats of the row.
                    for seat in range(1, screening.room.seats_per_row + 1):
                        # A seat is available when no booking holds its key.
                        result[(row, seat)] = (screening_id, row, seat) not in self.bookings
                # Hand the availability map back.
                return result
        except ProcessingException:
            # Log the exception at this layer.
            logger.exception("Availability lookup failed")
            # Rethrow it unchanged.
            raise

    # Find a screening or fail.
    def _get_screening(self, screening_id):
        # Unknown screening: raise the generic exception.
        if screening_id not in self.screenings:
            raise ProcessingException("Unknown screening %s" % screening_id)
        # Known screening: return it.
        return self.screenings[screening_id]

    # Fail unless the seat exists in the room of the screening.
    def _check_seat_exists(self, screening, row, seat):
        # Row and seat must both be inside the room's grid.
        if not (1 <= row <= screening.room.rows and 1 <= seat <= screening.room.seats_per_row):
            raise ProcessingException("Seat %d of row %d does not exist" % (seat, row))
