# Seat reservation service for a cinema chain. Python 3, standard library only.

# Import the logging module so every layer can report the failures it sees
import logging
# Import dataclass and field to declare the room and screening holders
from dataclasses import dataclass, field

# Create a module-level logger shared by every class in this module
logger = logging.getLogger(__name__)


# Define the generic exception that every rejected operation raises
class ProcessingException(Exception):
    # Carry a readable message without exposing implementation details
    pass


# Describe a room by its number of rows and seats per row
@dataclass(frozen=True)
class Room:
    # Number of rows in the room, numbered from 1
    rows: int
    # Number of seats in each row, numbered from 1
    seats_per_row: int

    # Validate the room dimensions right after the room is built
    def __post_init__(self):
        # Check that the room has at least one row and one seat per row
        if self.rows < 1 or self.seats_per_row < 1:
            # Log the invalid dimensions before rejecting them
            logger.error("Invalid room dimensions: rows=%s seats_per_row=%s", self.rows, self.seats_per_row)
            # Reject the room with the generic processing exception
            raise ProcessingException("A room needs at least one row and one seat per row")

    # List every seat of the room as a (row, number) pair
    def seats(self):
        # Build the seat coordinates in row-major order, both numbered from 1
        return [(row, number) for row in range(1, self.rows + 1) for number in range(1, self.seats_per_row + 1)]


# Track one screening of a film in a room together with its seat bookings
@dataclass
class Screening:
    # Identifier of the screening
    screening_id: str
    # Room in which the screening takes place
    room: Room
    # Map of each booked (row, number) seat to the client who booked it
    bookings: dict = field(default_factory=dict)


# Coordinate screenings, seat bookings and seat availability
class ScreeningManager:
    # Start the manager with no screening registered
    def __init__(self):
        # Store the known screenings keyed by their identifier
        self._screenings = {}

    # Register a new screening of a room
    def schedule_screening(self, screening_id, room):
        # Check that no screening already uses this identifier
        if screening_id in self._screenings:
            # Log the duplicate identifier before rejecting it
            logger.error("Duplicate screening: %s", screening_id)
            # Reject the duplicate with the generic processing exception
            raise ProcessingException(f"Screening already exists: {screening_id}")
        # Create the screening and store it under its identifier
        self._screenings[screening_id] = Screening(screening_id, room)

    # Book a seat of a screening for a client
    def book_seat(self, screening_id, seat, client_id):
        # Check that the screening is known before touching its bookings
        if screening_id not in self._screenings:
            # Log the unknown identifier before rejecting it
            logger.error("Unknown screening: %s", screening_id)
            # Reject the booking with the generic processing exception
            raise ProcessingException(f"Unknown screening: {screening_id}")
        # Fetch the screening that the seat belongs to
        screening = self._screenings[screening_id]
        # Check that the seat exists in the room of the screening
        if seat not in screening.room.seats():
            # Log the missing seat before rejecting the booking
            logger.error("Seat %s does not exist in screening %s", seat, screening_id)
            # Reject the booking with the generic processing exception
            raise ProcessingException(f"Seat {seat} does not exist in screening {screening_id}")
        # Check that nobody has already booked this seat
        if seat in screening.bookings:
            # Log the double booking before rejecting it
            logger.error("Seat %s already booked in screening %s", seat, screening_id)
            # Reject the booking with the generic processing exception
            raise ProcessingException(f"Seat {seat} is already booked for screening {screening_id}")
        # Record the client as the holder of the seat
        screening.bookings[seat] = client_id

    # Report the availability of every seat of a screening
    def get_seat_availability(self, screening_id):
        # Check that the screening is known before reporting on it
        if screening_id not in self._screenings:
            # Log the unknown identifier before rejecting it
            logger.error("Unknown screening: %s", screening_id)
            # Reject the query with the generic processing exception
            raise ProcessingException(f"Unknown screening: {screening_id}")
        # Fetch the screening whose seats are reported
        screening = self._screenings[screening_id]
        # Map each seat of the room to True when it is still free
        return {seat: seat not in screening.bookings for seat in screening.room.seats()}
