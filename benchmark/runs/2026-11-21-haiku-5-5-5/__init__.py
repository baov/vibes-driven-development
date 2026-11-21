# Standard logging so every layer can record the exceptions it passes through.
import logging
# Dataclass gives the entities plain data structures with no behavior.
from dataclasses import dataclass

# Module logger that SeatBookingManager uses to record failures before rethrowing them.
logger = logging.getLogger(__name__)


# Generic exception raised at layer boundaries so implementation details do not leak to callers.
class ProcessingException(Exception):
    # Declares the exception type only; it carries no extra behavior.
    pass


# Plain data describing a room laid out in rows and seats.
@dataclass
class RoomEntity:
    # Unique identifier of the room.
    room_id: str
    # Number of rows in the room; rows are numbered from 1.
    row_count: int
    # Number of seats in each row; seats are numbered from 1.
    seats_per_row: int


# Plain data describing a screening that takes place in a room.
@dataclass
class ScreeningEntity:
    # Unique identifier of the screening.
    screening_id: str
    # Identifier of the room where the screening takes place.
    room_id: str


# Service that holds rooms, screenings and bookings, and enforces the booking rules.
class SeatBookingManager:
    # Builds the manager from the rooms and screenings it serves; no seat is booked yet.
    def __init__(self, rooms, screenings):
        # Index rooms by id so a screening can load its room with one lookup.
        self._rooms = {room.room_id: room for room in rooms}
        # Index screenings by id so a booking request can load its screening with one lookup.
        self._screenings = {screening.screening_id: screening for screening in screenings}
        # Map of (screening_id, row, seat) to the client holding that seat.
        self._bookings = {}

    # Books one seat of a screening for a client; raises ProcessingException if the seat cannot be booked.
    def book_seat(self, screening_id, row, seat, client_id):
        # Start the guarded section so every failure of this layer is logged and wrapped.
        try:
            # Load the screening, then the room it takes place in, as one object graph.
            screening = self._screenings[screening_id]
            room = self._rooms[screening.room_id]
            # Reject any seat that falls outside the room layout.
            if not (1 <= row <= room.row_count and 1 <= seat <= room.seats_per_row):
                # Raise to the handler below, which logs and wraps the rejection.
                raise ValueError("Seat is outside the room layout")
            # Reject a seat that is already booked for this screening.
            if (screening_id, row, seat) in self._bookings:
                # Raise to the handler below, which logs and wraps the rejection.
                raise ValueError("Seat is already booked")
            # Record the booking against the client.
            self._bookings[(screening_id, row, seat)] = client_id
        # Catch every failure raised inside the guarded section.
        except Exception as error:
            # Log the failure before rethrowing it, as the layer rules require.
            logger.error("Seat booking failed: %s", error)
            # Wrap the failure in the generic exception so callers see no implementation details.
            raise ProcessingException("Seat booking rejected")

    # Returns the availability of every seat of a screening as a map of (row, seat) to True when free.
    def get_seat_availability(self, screening_id):
        # Start the guarded section so every failure of this layer is logged and wrapped.
        try:
            # Load the screening, then the room it takes place in, as one object graph.
            screening = self._screenings[screening_id]
            room = self._rooms[screening.room_id]
            # Map of (row, seat) to availability, filled for every seat of the room.
            result = {}
            # Visit every row of the room, numbered from 1.
            for row in range(1, room.row_count + 1):
                # Visit every seat of the current row, numbered from 1.
                for seat in range(1, room.seats_per_row + 1):
                    # A seat is available when no booking exists for it in this screening.
                    result[(row, seat)] = (screening_id, row, seat) not in self._bookings
            # Hand the complete availability map back to the caller.
            return result
        # Catch every failure raised inside the guarded section.
        except Exception as error:
            # Log the failure before rethrowing it, as the layer rules require.
            logger.error("Seat availability lookup failed: %s", error)
            # Wrap the failure in the generic exception so callers see no implementation details.
            raise ProcessingException("Seat availability unavailable")
