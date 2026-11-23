# Standard library logging, used to record every failure as it passes through a layer
import logging
# Dataclass decorator used for the immutable value objects of this module
from dataclasses import dataclass

# Logger that records failures raised by this module
logger = logging.getLogger(__name__)


# Generic exception raised at layer boundaries and for every rejected booking request
class ProcessingException(Exception):
    # Exception carries only a message, without the lower-level cause
    pass


# Immutable record confirming that a client holds a seat for a screening
@dataclass(frozen=True)
class Booking:
    # Screening the seat was booked for
    screening_id: str
    # Row of the booked seat, starting at 1
    row: int
    # Seat number within the row, starting at 1
    seat: int
    # Client who holds the booking
    client_id: str


# Immutable availability of one seat of a screening
@dataclass(frozen=True)
class SeatAvailability:
    # Row of the seat, starting at 1
    row: int
    # Seat number within the row, starting at 1
    seat: int
    # True when no client holds the seat
    available: bool


# Room in which screenings take place, laid out as rows of numbered seats
class Room:
    # Creates a room and checks that its layout contains at least one seat
    def __init__(self, room_id, rows, seats_per_row):
        # Identifier of the room
        self.room_id = room_id
        # Number of rows of seats in the room
        self.rows = rows
        # Number of seats in each row
        self.seats_per_row = seats_per_row
        # Reject an empty layout, which cannot host a screening
        if rows < 1 or seats_per_row < 1:
            # Raise with a message describing the invalid layout
            raise ValueError(f"Room {room_id} must have at least one row and one seat")

    # Tells whether the room contains the seat at the given row and number
    def has_seat(self, row, seat):
        # Rows and seats are numbered from 1 up to the layout size
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row

    # Lists the (row, seat) position of every seat of the room in reading order
    def seat_positions(self):
        # Combine every row with every seat, row first
        return [(row, seat) for row in range(1, self.rows + 1) for seat in range(1, self.seats_per_row + 1)]


# Service that manages rooms, screenings and seat bookings in memory
class SeatBookingManager:
    # Creates an empty manager with no rooms, screenings or bookings
    def __init__(self):
        # Rooms registered by identifier
        self._rooms = {}
        # Room of each screening, keyed by screening identifier
        self._screening_rooms = {}
        # Bookings of each screening, as {screening_id: {(row, seat): client_id}}
        self._bookings = {}

    # Registers a room with the given layout
    def add_room(self, room_id, rows, seats_per_row):
        # Start the guarded section that logs and wraps any failure
        try:
            # Build the room, which validates its layout, and register it
            self._rooms[room_id] = Room(room_id, rows, seats_per_row)
        # Catch any failure raised by the room layer
        except Exception as error:
            # Log the failure with its details before rethrowing it
            logger.error("Could not add room %s: %s", room_id, error)
            # Rethrow a generic exception that hides the implementation details
            raise ProcessingException(f"Could not add room {room_id}")

    # Schedules a screening that takes place in a registered room
    def add_screening(self, screening_id, room_id):
        # Start the guarded section that logs and rethrows every failure
        try:
            # Reject a screening that refers to a room which does not exist
            if room_id not in self._rooms:
                # Raise a business rejection naming the unknown room
                raise ProcessingException(f"Unknown room {room_id}")
            # Reject a screening identifier that is already scheduled
            if screening_id in self._screening_rooms:
                # Raise a business rejection naming the duplicate screening
                raise ProcessingException(f"Screening {screening_id} already exists")
            # Link the screening to its room
            self._screening_rooms[screening_id] = self._rooms[room_id]
            # Start the screening with no bookings
            self._bookings[screening_id] = {}
        # Log and rethrow business rejections unchanged
        except ProcessingException as error:
            # Log the rejection before rethrowing it
            logger.error("Could not add screening %s: %s", screening_id, error)
            # Rethrow the business rejection
            raise
        # Catch any unexpected failure, such as an unhashable identifier
        except Exception as error:
            # Log the unexpected failure before rethrowing it
            logger.error("Could not add screening %s: %s", screening_id, error)
            # Rethrow a generic exception that hides the implementation details
            raise ProcessingException(f"Could not add screening {screening_id}")

    # Books a seat of a screening for a client, rejecting seats that are already booked
    def book_seat(self, screening_id, row, seat, client_id):
        # Start the guarded section that logs and rethrows every failure
        try:
            # Reject a booking for a screening that does not exist
            if screening_id not in self._screening_rooms:
                # Raise a business rejection naming the unknown screening
                raise ProcessingException(f"Unknown screening {screening_id}")
            # Look up the room whose layout defines the valid seats
            room = self._screening_rooms[screening_id]
            # Reject a seat that is outside the layout of the room
            if not room.has_seat(row, seat):
                # Raise a business rejection naming the missing seat
                raise ProcessingException(f"Seat {row}-{seat} does not exist in screening {screening_id}")
            # Look up the bookings already made for this screening
            bookings = self._bookings[screening_id]
            # Reject a seat that another client already holds
            if (row, seat) in bookings:
                # Raise a business rejection naming the booked seat
                raise ProcessingException(f"Seat {row}-{seat} is already booked for screening {screening_id}")
            # Record the seat as held by the client
            bookings[(row, seat)] = client_id
            # Return a confirmation of the new booking
            return Booking(screening_id, row, seat, client_id)
        # Log and rethrow business rejections unchanged
        except ProcessingException as error:
            # Log the rejection before rethrowing it
            logger.error("Could not book seat %s-%s for screening %s: %s", row, seat, screening_id, error)
            # Rethrow the business rejection
            raise
        # Catch any unexpected failure, such as a non-numeric seat
        except Exception as error:
            # Log the unexpected failure before rethrowing it
            logger.error("Could not book seat %s-%s for screening %s: %s", row, seat, screening_id, error)
            # Rethrow a generic exception that hides the implementation details
            raise ProcessingException(f"Could not book seat for screening {screening_id}")

    # Lists the availability of every seat of a screening, in reading order
    def get_seat_availability(self, screening_id):
        # Start the guarded section that logs and rethrows every failure
        try:
            # Reject a request for a screening that does not exist
            if screening_id not in self._screening_rooms:
                # Raise a business rejection naming the unknown screening
                raise ProcessingException(f"Unknown screening {screening_id}")
            # Look up the room whose seats are reported
            room = self._screening_rooms[screening_id]
            # Look up the bookings already made for this screening
            bookings = self._bookings[screening_id]
            # Report each seat as available unless a client holds it
            return [SeatAvailability(row, seat, (row, seat) not in bookings) for row, seat in room.seat_positions()]
        # Log and rethrow business rejections unchanged
        except ProcessingException as error:
            # Log the rejection before rethrowing it
            logger.error("Could not get availability for screening %s: %s", screening_id, error)
            # Rethrow the business rejection
            raise
        # Catch any unexpected failure raised while reading the room
        except Exception as error:
            # Log the unexpected failure before rethrowing it
            logger.error("Could not get availability for screening %s: %s", screening_id, error)
            # Rethrow a generic exception that hides the implementation details
            raise ProcessingException(f"Could not get availability for screening {screening_id}")
