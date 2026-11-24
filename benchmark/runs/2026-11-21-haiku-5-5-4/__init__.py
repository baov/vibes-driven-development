# Standard library logging, used to record every failure at each layer
import logging
# Standard library dataclasses, used to declare plain data entities
from dataclasses import dataclass

# Module logger shared by every layer of the service
logger = logging.getLogger(__name__)


# Generic exception raised at the service boundary so implementation details do not leak
class ProcessingException(Exception):
    # Empty body: the class only needs to exist as a distinct exception type
    pass


# Plain data entity describing a room laid out as rows of seats
@dataclass
class RoomData:
    # Unique identifier of the room
    room_id: str
    # Number of rows in the room, numbered from 1
    rows: int
    # Number of seats in each row, numbered from 1
    seats_per_row: int


# Plain data entity linking a screening to the room where it takes place
@dataclass
class ScreeningData:
    # Unique identifier of the screening
    screening_id: str
    # Identifier of the room hosting the screening
    room_id: str


# Plain data entity recording that a client holds a given seat for a screening
@dataclass
class BookingData:
    # Identifier of the screening the seat is booked for
    screening_id: str
    # Row of the booked seat, numbered from 1
    row: int
    # Seat number within the row, numbered from 1
    seat: int
    # Identifier of the client who booked the seat
    client_id: str


# Service that owns rooms, screenings and bookings in memory and enforces the booking rules
class SeatBookingManager:
    # Create empty registries for rooms, screenings and bookings
    def __init__(self):
        # Registry of rooms keyed by room_id
        self._rooms = {}
        # Registry of screenings keyed by screening_id
        self._screenings = {}
        # Registry of bookings keyed by (screening_id, row, seat)
        self._bookings = {}

    # Register a room with the given number of rows and seats per row
    def add_room(self, room_id, rows, seats_per_row):
        # Open the guarded block so every failure below is logged and rethrown wrapped
        try:
            # Reject a room_id that is already registered
            if room_id in self._rooms:
                # Raise the rejection for a duplicate room
                raise ProcessingException(f"Room {room_id} already exists")
            # Store the new room in the registry
            self._rooms[room_id] = RoomData(room_id, rows, seats_per_row)
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure at this layer before rethrowing
            logger.exception("add_room failed")
            # Rethrow as the generic exception, keeping only the message
            raise ProcessingException(str(error))

    # Register a screening that takes place in an already registered room
    def add_screening(self, screening_id, room_id):
        # Open the guarded block so every failure below is logged and rethrown wrapped
        try:
            # Reject a screening_id that is already registered
            if screening_id in self._screenings:
                # Raise the rejection for a duplicate screening
                raise ProcessingException(f"Screening {screening_id} already exists")
            # Reject a screening whose room is not registered
            if room_id not in self._rooms:
                # Raise the rejection for an unknown room
                raise ProcessingException(f"Unknown room {room_id}")
            # Store the new screening in the registry
            self._screenings[screening_id] = ScreeningData(screening_id, room_id)
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure at this layer before rethrowing
            logger.exception("add_screening failed")
            # Rethrow as the generic exception, keeping only the message
            raise ProcessingException(str(error))

    # Book a seat for a client; rejects unknown screenings, nonexistent seats and seats already booked
    def book_seat(self, screening_id, client_id, row, seat):
        # Open the guarded block so every failure below is logged and rethrown wrapped
        try:
            # Reject a screening that is not registered
            if screening_id not in self._screenings:
                # Raise the rejection for an unknown screening
                raise ProcessingException(f"Unknown screening {screening_id}")
            # Look up the room hosting the screening to know its layout
            room = self._rooms[self._screenings[screening_id].room_id]
            # Reject a seat that falls outside the rows and seats of the room
            if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
                # Raise the rejection for a seat that does not exist
                raise ProcessingException(f"Seat {row}-{seat} does not exist in screening {screening_id}")
            # Build the key identifying this seat for this screening
            key = (screening_id, row, seat)
            # Reject the booking if the seat is already held
            if key in self._bookings:
                # Raise the rejection for a seat that is already booked
                raise ProcessingException(f"Seat {row}-{seat} already booked for screening {screening_id}")
            # Record the booking so the seat is no longer available
            self._bookings[key] = BookingData(screening_id, row, seat, client_id)
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure at this layer before rethrowing
            logger.exception("book_seat failed")
            # Rethrow as the generic exception, keeping only the message
            raise ProcessingException(str(error))

    # Return the availability of every seat of a screening, ordered by row then seat
    def get_seat_availability(self, screening_id):
        # Open the guarded block so every failure below is logged and rethrown wrapped
        try:
            # Reject a screening that is not registered
            if screening_id not in self._screenings:
                # Raise the rejection for an unknown screening
                raise ProcessingException(f"Unknown screening {screening_id}")
            # Look up the room hosting the screening to know its layout
            room = self._rooms[self._screenings[screening_id].room_id]
            # Start the list that will hold one entry per seat
            availability = []
            # Walk every row of the room, numbered from 1
            for row in range(1, room.rows + 1):
                # Walk every seat of the current row, numbered from 1
                for seat in range(1, room.seats_per_row + 1):
                    # Build the key identifying this seat for this screening
                    key = (screening_id, row, seat)
                    # Describe the seat with its position and whether it is still free
                    info = {"row": row, "seat": seat, "available": key not in self._bookings}
                    # Add the seat description to the result
                    availability.append(info)
            # Return the availability of every seat
            return availability
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure at this layer before rethrowing
            logger.exception("get_seat_availability failed")
            # Rethrow as the generic exception, keeping only the message
            raise ProcessingException(str(error))
