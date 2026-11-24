# Import the logging module to record failures at every layer
import logging

# Create a module logger that every layer of this package writes to
logger = logging.getLogger(__name__)


# Generic exception raised at layer boundaries so implementation details do not leak
class ProcessingException(Exception):
    pass


# Raised when a client tries to book a seat that another booking already holds
class SeatAlreadyBookedException(ProcessingException):
    pass


# Manages screenings, each held in a room of rows and seats, and the seat bookings made for them
class SeatBookingManager:
    # Create a manager with no screenings registered yet
    def __init__(self):
        # Map each screening id to its room layout and the bookings made so far
        self._screenings = {}

    # Register a screening held in a room with the given number of rows and seats per row
    def add_screening(self, screening_id, rows, seats_per_row):
        # Check whether a screening with this id is already registered
        if screening_id in self._screenings:
            # Log the duplicate registration before rejecting it
            logger.error("Screening %s is already registered", screening_id)
            # Reject the registration so existing bookings are not wiped
            raise ProcessingException(f"Screening already registered: {screening_id}")
        # Store the room layout with an empty booking map for the new screening
        self._screenings[screening_id] = {"rows": rows, "seats_per_row": seats_per_row, "bookings": {}}

    # Book the seat at the given row and seat number of a screening for a client
    def book_seat(self, screening_id, client_id, row, seat):
        # Try to find the screening in the registry
        try:
            # Fetch the room layout and bookings of the screening
            screening = self._screenings[screening_id]
        # Handle the case where the screening id is unknown
        except KeyError:
            # Log the unknown screening before rejecting the request
            logger.error("Unknown screening %s", screening_id)
            # Wrap the lookup failure in a generic exception without exposing the dictionary lookup
            raise ProcessingException(f"Unknown screening: {screening_id}")
        # Check that the requested row and seat exist in the room
        if not (1 <= row <= screening["rows"] and 1 <= seat <= screening["seats_per_row"]):
            # Log the invalid seat before rejecting it
            logger.error("Seat %s-%s does not exist for screening %s", row, seat, screening_id)
            # Reject the seat because it is outside the room layout
            raise ProcessingException(f"Seat {row}-{seat} does not exist for screening {screening_id}")
        # Check whether another booking already holds this seat
        if (row, seat) in screening["bookings"]:
            # Log the conflicting booking before rejecting it
            logger.error("Seat %s-%s already booked for screening %s", row, seat, screening_id)
            # Reject the booking because the seat is taken
            raise SeatAlreadyBookedException(f"Seat {row}-{seat} already booked for screening {screening_id}")
        # Record the client as the holder of the seat
        screening["bookings"][(row, seat)] = client_id

    # Return the availability of every seat of a screening, ordered by row then seat
    def get_seat_availability(self, screening_id):
        # Try to find the screening in the registry
        try:
            # Fetch the room layout and bookings of the screening
            screening = self._screenings[screening_id]
        # Handle the case where the screening id is unknown
        except KeyError:
            # Log the unknown screening before rejecting the request
            logger.error("Unknown screening %s", screening_id)
            # Wrap the lookup failure in a generic exception without exposing the dictionary lookup
            raise ProcessingException(f"Unknown screening: {screening_id}")
        # Start with an empty list of seat availability entries
        availability = []
        # Visit every row of the room, numbered from 1
        for row in range(1, screening["rows"] + 1):
            # Visit every seat of the current row, numbered from 1
            for seat in range(1, screening["seats_per_row"] + 1):
                # Record the seat with a flag telling whether no booking holds it
                availability.append({"row": row, "seat": seat, "available": (row, seat) not in screening["bookings"]})
        # Return the full list of seat availability entries
        return availability
