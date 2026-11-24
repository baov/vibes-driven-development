# Import logging to record every exception before it leaves this module.
import logging
# Import dataclass and field to declare plain data entities.
from dataclasses import dataclass, field

# Create the module logger used by the service layer.
logger = logging.getLogger(__name__)


# Declare ProcessingException as the generic failure exposed to callers.
class ProcessingException(Exception):
    # Keep the body empty: the message alone carries the reason for the failure.
    pass


# Declare Room as a plain data class holding the seat layout.
@dataclass
# Define the Room entity.
class Room:
    # Number of rows in the room, numbered from 1.
    rows: int
    # Number of seats in each row, numbered from 1.
    seats_per_row: int


# Declare Screening as a plain data class holding its room and its bookings.
@dataclass
# Define the Screening entity.
class Screening:
    # Room in which the screening takes place.
    room: Room
    # Booked seats keyed by (row, seat), with the booking client id as value.
    bookings: dict = field(default_factory=dict)


# Role Manager: owns the seat booking rules and keeps no state of its own.
class SeatBookingManager:
    # Books one seat of the screening for the client, rejecting invalid or already booked seats.
    def book_seat(self, screening, client_id, row, seat):
        # Start the guarded block so every failure is logged before it leaves this layer.
        try:
            # Read the room in which the screening takes place.
            room = screening.room
            # Reject a seat that does not exist in the room.
            if not (1 <= row <= room.rows and 1 <= seat <= room.seats_per_row):
                # Raise the generic exception for a seat outside the room.
                raise ProcessingException("seat does not exist in the room")
            # Reject a seat that is already booked.
            if (row, seat) in screening.bookings:
                # Raise the generic exception for a seat that is already booked.
                raise ProcessingException("seat is already booked")
            # Record the booking under the seat key for the client.
            screening.bookings[(row, seat)] = client_id
        # Catch the domain rejections raised above.
        except ProcessingException as exception:
            # Log the rejection at this layer.
            logger.error("booking rejected: %s", exception)
            # Rethrow the rejection unchanged.
            raise
        # Catch any lower-level failure, such as a missing screening.
        except Exception:
            # Log the lower-level failure together with its traceback.
            logger.exception("booking failed")
            # Wrap the lower-level failure in the generic exception without exposing its cause.
            raise ProcessingException("seat booking failed") from None

    # Returns the availability of every seat of the screening, keyed by (row, seat), True when free.
    def get_seat_availability(self, screening):
        # Start the guarded block so every failure is logged before it leaves this layer.
        try:
            # Read the room in which the screening takes place.
            room = screening.room
            # Start an empty mapping that will hold the availability of each seat.
            result = {}
            # Visit every row of the room, numbered from 1.
            for row in range(1, room.rows + 1):
                # Visit every seat of the row, numbered from 1.
                for seat in range(1, room.seats_per_row + 1):
                    # A seat is available when no booking exists under its key.
                    result[(row, seat)] = (row, seat) not in screening.bookings
            # Return the availability of every seat.
            return result
        # Catch any lower-level failure, such as a missing screening.
        except Exception:
            # Log the lower-level failure together with its traceback.
            logger.exception("seat availability lookup failed")
            # Wrap the lower-level failure in the generic exception without exposing its cause.
            raise ProcessingException("seat availability lookup failed") from None
