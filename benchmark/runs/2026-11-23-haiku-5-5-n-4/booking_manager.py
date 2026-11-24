# Import the standard logging module used to record every failure before it is rethrown
import logging

# Create the module logger so each failure is traceable to this module
logger = logging.getLogger(__name__)


# Define the generic exception raised at the service boundary, hiding implementation details
class ProcessingException(Exception):
    # Keep the class body empty: the message alone is the payload
    pass


# Define the exception raised when a client tries to book a seat that is already held
class SeatAlreadyBookedException(ProcessingException):
    # Keep the class body empty: the subclass only exists to let callers tell the case apart
    pass


# Define the manager that keeps rooms, screenings and seat bookings, and enforces one holder per seat
class BookingManager:
    # Start the manager with no rooms and no screenings
    def __init__(self):
        # Create the map from room id to its number of rows and seats per row
        self.rooms = {}
        # Create the map from screening id to its seat grid and the seats booked so far
        self.screenings = {}

    # Register a room with the given number of rows and seats per row
    def add_room(self, room_id, rows, seats_per_row):
        # Check that the room has at least one row and one seat
        if rows < 1 or seats_per_row < 1:
            # Log the invalid room dimensions before rejecting them
            logger.error("Invalid room %s: rows=%s seats_per_row=%s", room_id, rows, seats_per_row)
            # Raise the generic exception to the caller
            raise ProcessingException("Room must have at least one row and one seat")
        # Store the room dimensions under its id
        self.rooms[room_id] = {"rows": rows, "seats_per_row": seats_per_row}

    # Schedule a screening in an existing room, with no seat booked yet
    def add_screening(self, screening_id, room_id):
        # Check that the room exists before scheduling a screening in it
        if room_id not in self.rooms:
            # Log the unknown room reference before rejecting it
            logger.error("Unknown room %s for screening %s", room_id, screening_id)
            # Raise the generic exception to the caller
            raise ProcessingException(f"Unknown room {room_id}")
        # Read the dimensions of the room the screening takes place in
        room = self.rooms[room_id]
        # Copy the room dimensions into the screening, with an empty map of booked seats
        self.screenings[screening_id] = {"rows": room["rows"], "seats_per_row": room["seats_per_row"], "booked": {}}

    # Book one seat of a screening for a client, rejecting seats that are missing or already taken
    def book_seat(self, screening_id, row, seat, client_id):
        # Check that the screening was scheduled
        if screening_id not in self.screenings:
            # Log the unknown screening before rejecting it
            logger.error("Unknown screening %s", screening_id)
            # Raise the generic exception to the caller
            raise ProcessingException(f"Unknown screening {screening_id}")
        # Read the seat grid and booked seats of the screening
        screening = self.screenings[screening_id]
        # Check that the seat exists within the rows and seats of the room
        if not (1 <= row <= screening["rows"] and 1 <= seat <= screening["seats_per_row"]):
            # Log the missing seat before rejecting it
            logger.error("Seat %s-%s does not exist in screening %s", row, seat, screening_id)
            # Raise the generic exception to the caller
            raise ProcessingException(f"Seat {row}-{seat} does not exist")
        # Build the key identifying the seat by its row and seat number
        seat_key = (row, seat)
        # Check that no client holds the seat yet
        if seat_key in screening["booked"]:
            # Log the double booking before rejecting it
            logger.error("Seat %s-%s already booked in screening %s", row, seat, screening_id)
            # Raise the dedicated exception so the caller can tell the case apart
            raise SeatAlreadyBookedException(f"Seat {row}-{seat} is already booked")
        # Record the client as the holder of the seat
        screening["booked"][seat_key] = client_id

    # Return the availability of every seat of a screening, row by row
    def seat_availability(self, screening_id):
        # Check that the screening was scheduled
        if screening_id not in self.screenings:
            # Log the unknown screening before rejecting it
            logger.error("Unknown screening %s", screening_id)
            # Raise the generic exception to the caller
            raise ProcessingException(f"Unknown screening {screening_id}")
        # Read the seat grid and booked seats of the screening
        screening = self.screenings[screening_id]
        # Create the list that will hold one entry per seat
        availability = []
        # Walk through every row of the room
        for row in range(1, screening["rows"] + 1):
            # Walk through every seat of the current row
            for seat in range(1, screening["seats_per_row"] + 1):
                # Record the seat with a flag telling whether it is still free
                availability.append({"row": row, "seat": seat, "available": (row, seat) not in screening["booked"]})
        # Return the availability of all seats
        return availability
