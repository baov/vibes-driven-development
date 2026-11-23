# Seat booking for screenings: registers screenings, books seats and reports seat availability
import logging
# Plain data structures describing the room, the screening and the seats
from dataclasses import dataclass

# Logger for this layer, so every failure passing through it is recorded
logger = logging.getLogger(__name__)


# Room a screening takes place in, with rows and seats numbered from 1
@dataclass
class Room:
    # Display name of the room
    name: str
    # Number of rows of seats
    rows: int
    # Number of seats in each row
    seats_per_row: int


# Screening that takes place in a room
@dataclass
class Screening:
    # Identifier of the screening
    screening_id: str
    # Room where the screening takes place
    room: Room


# Seat booked by a client for a screening
@dataclass
class Booking:
    # Screening the seat is booked for
    screening_id: str
    # Row of the booked seat
    row: int
    # Number of the booked seat within its row
    seat: int
    # Client who booked the seat
    client_id: str


# Availability of one seat of a screening
@dataclass
class Seat:
    # Row of the seat
    row: int
    # Number of the seat within its row
    number: int
    # Whether the seat can still be booked for the screening
    available: bool


# Generic failure of the booking service, hides implementation details from callers
class ProcessingException(Exception):
    pass


# Raised when a client tries to book a seat already taken for the screening
class SeatAlreadyBookedException(ProcessingException):
    pass


# Books seats for screenings and reports the availability of their seats
class BookingManager:

    # Create a manager with no screenings and no bookings
    def __init__(self):
        # Screenings registered with the manager, keyed by screening id
        self._screenings = {}
        # Bookings made so far, keyed by (screening id, row, seat)
        self._bookings = {}

    # Register a screening so that seats can be booked for it
    def add_screening(self, screening):
        try:
            # Store the screening under its identifier
            self._screenings[screening.screening_id] = screening
        except Exception as error:
            # Record the failure at this layer
            logger.error("add_screening failed: %s", error)
            # Wrap it so implementation details do not leak
            raise ProcessingException("Could not add screening")

    # Book a seat of a screening for a client, rejecting unknown screenings, invalid seats and seats already taken
    def book_seat(self, screening_id, row, seat, client_id):
        try:
            # Look up the screening, None when it was never registered
            screening = self._screenings.get(screening_id)
            # Reject bookings for screenings that do not exist
            if screening is None:
                raise ProcessingException("Unknown screening")
            # Read the room the screening takes place in
            room = screening.room
            # Reject seats outside the rows and seats of the room
            if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
                raise ProcessingException("Seat does not exist in the room")
            # Key identifying the seat for this screening
            key = (screening_id, row, seat)
            # Reject the booking when the seat is already taken
            if key in self._bookings:
                raise SeatAlreadyBookedException("Seat is already booked")
            # Build the booking record
            booking = Booking(screening_id, row, seat, client_id)
            # Store the booking so later availability checks see the seat as taken
            self._bookings[key] = booking
            # Return the stored booking to the caller
            return booking
        except ProcessingException as error:
            # Record the rejection, then pass it on unchanged
            logger.error("book_seat rejected: %s", error)
            raise
        except Exception as error:
            # Record the unexpected failure at this layer
            logger.error("book_seat failed: %s", error)
            # Wrap it so implementation details do not leak
            raise ProcessingException("Could not book seat")

    # Report every seat of the screening's room, row by row, with whether it can still be booked
    def get_seat_availability(self, screening_id):
        try:
            # Look up the screening, None when it was never registered
            screening = self._screenings.get(screening_id)
            # Reject queries for screenings that do not exist
            if screening is None:
                raise ProcessingException("Unknown screening")
            # Read the room the screening takes place in
            room = screening.room
            # Accumulator for the availability of each seat
            seats = []
            # Visit every row of the room
            for row in range(1, room.rows + 1):
                # Visit every seat of the row
                for number in range(1, room.seats_per_row + 1):
                    # A seat is available when no booking exists for it in this screening
                    available = (screening_id, row, number) not in self._bookings
                    # Record the availability of this seat
                    seats.append(Seat(row, number, available))
            # Return the availability of all seats
            return seats
        except ProcessingException as error:
            # Record the rejection, then pass it on unchanged
            logger.error("get_seat_availability rejected: %s", error)
            raise
        except Exception as error:
            # Record the unexpected failure at this layer
            logger.error("get_seat_availability failed: %s", error)
            # Wrap it so implementation details do not leak
            raise ProcessingException("Could not read seat availability")
