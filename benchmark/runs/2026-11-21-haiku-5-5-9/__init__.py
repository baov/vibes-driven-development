# Standard library logging, used to record every failure before it is rethrown
import logging
# Dataclass decorator and field helper for the plain data entity
from dataclasses import dataclass, field

# Module-level logger that records failures raised in this module
logger = logging.getLogger(__name__)


# Generic failure raised at the service boundary, hiding implementation details
class ProcessingException(Exception):
    # Marker body: the exception carries only its message
    pass


# Plain data structure describing one screening and the seats booked for it
@dataclass
class ScreeningEntity:
    # Unique identifier of the screening
    screening_id: str
    # Number of rows in the room where the screening takes place
    rows: int
    # Number of seats in each row of the room
    seats_per_row: int
    # Set of booked seats, each stored as a (row, seat) tuple
    booked_seats: set = field(default_factory=set)


# Business rules for booking seats and reading the availability of every seat
class SeatBookingManager:
    # Create the manager with an empty registry of screenings
    def __init__(self):
        # Registry of screenings keyed by their identifier
        self.screenings = {}

    # Register a new screening in a room of the given size
    def add_screening(self, screening_id, rows, seats_per_row):
        # Start the block that logs and rethrows any failure of this method
        try:
            # Reject the registration when the identifier is already in use
            if screening_id in self.screenings:
                # Raise the generic failure describing the duplicate identifier
                raise ProcessingException(f"Screening {screening_id} already exists")
            # Store the new screening with no seat booked yet
            self.screenings[screening_id] = ScreeningEntity(screening_id, rows, seats_per_row)
        # Catch the failures raised by this layer
        except ProcessingException as exception:
            # Log the failure before it leaves this layer
            logger.error(str(exception))
            # Rethrow the same failure to the caller
            raise

    # Book one seat of a screening, rejecting unknown, out-of-room or already booked seats
    def book_seat(self, screening_id, row, seat):
        # Start the block that logs and rethrows any failure of this method
        try:
            # Look up the screening, or None when the identifier is unknown
            screening = self.screenings.get(screening_id)
            # Reject the booking when no screening has this identifier
            if screening is None:
                # Raise the generic failure describing the unknown identifier
                raise ProcessingException(f"Unknown screening {screening_id}")
            # Reject the booking when the seat lies outside the room layout
            if not (0 <= row < screening.rows and 0 <= seat < screening.seats_per_row):
                # Raise the generic failure describing the seat outside the room
                raise ProcessingException(f"Seat {row}-{seat} is outside the room")
            # Reject the booking when the seat is already taken
            if (row, seat) in screening.booked_seats:
                # Raise the generic failure describing the seat already booked
                raise ProcessingException(f"Seat {row}-{seat} is already booked")
            # Record the seat as booked
            screening.booked_seats.add((row, seat))
        # Catch the failures raised by this layer
        except ProcessingException as exception:
            # Log the failure before it leaves this layer
            logger.error(str(exception))
            # Rethrow the same failure to the caller
            raise

    # Report whether every seat of a screening is still free
    def get_seat_availability(self, screening_id):
        # Start the block that logs and rethrows any failure of this method
        try:
            # Look up the screening, or None when the identifier is unknown
            screening = self.screenings.get(screening_id)
            # Reject the query when no screening has this identifier
            if screening is None:
                # Raise the generic failure describing the unknown identifier
                raise ProcessingException(f"Unknown screening {screening_id}")
            # Start the map from each (row, seat) to whether it is free
            availability = {}
            # Visit every row of the room
            for row in range(screening.rows):
                # Visit every seat within the current row
                for seat in range(screening.seats_per_row):
                    # Record that the seat is free when it is not in the booked seats
                    availability[(row, seat)] = (row, seat) not in screening.booked_seats
            # Return the availability of every seat of the screening
            return availability
        # Catch the failures raised by this layer
        except ProcessingException as exception:
            # Log the failure before it leaves this layer
            logger.error(str(exception))
            # Rethrow the same failure to the caller
            raise
