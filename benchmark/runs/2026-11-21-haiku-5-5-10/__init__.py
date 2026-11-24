# Standard library logging, used to record every rejected operation before it is raised
import logging

# Module logger named after this module, so each log record identifies where it came from
logger = logging.getLogger(__name__)


# Generic exception raised for every rejected operation, so callers never see internal details
class ProcessingException(Exception):
    # Intentionally empty: the message passed to the constructor is the whole payload
    pass


# Service that tracks screenings, the seats of their rooms and the seats booked by clients
class SeatBookingManager:
    # Creates a service with no screenings and no bookings
    def __init__(self):
        # Maps each screening id to the (rows, seats_per_row) layout of its room
        self._rooms = {}
        # Maps (screening id, row, seat) to the id of the client holding that seat
        self._bookings = {}

    # Registers a screening together with the layout of the room it takes place in
    def register_screening(self, screening_id, rows, seats_per_row):
        # Reject a room that has no row or no seat per row, since it could never hold a booking
        if rows < 1 or seats_per_row < 1:
            # Record the rejected registration before raising
            logger.error("Rejected screening %s: room has no seats", screening_id)
            # Raise the generic exception describing the invalid room
            raise ProcessingException("invalid room layout")
        # Reject a screening already registered, since replacing its room would orphan its bookings
        if screening_id in self._rooms:
            # Record the rejected registration before raising
            logger.error("Rejected screening %s: already registered", screening_id)
            # Raise the generic exception describing the duplicate
            raise ProcessingException("screening already registered")
        # Store the room layout under the screening id
        self._rooms[screening_id] = (rows, seats_per_row)

    # Books one seat of a screening for a client, rejecting unknown screenings, missing seats and seats already taken
    def book_seat(self, screening_id, row, seat, client_id):
        # Reject screenings that were never registered
        if screening_id not in self._rooms:
            # Record the rejected booking before raising
            logger.error("Rejected booking on screening %s: unknown screening", screening_id)
            # Raise the generic exception describing the unknown screening
            raise ProcessingException("unknown screening")
        # Read the layout of the room where the screening takes place
        rows, seats_per_row = self._rooms[screening_id]
        # Reject a row or seat that lies outside the room
        if not (1 <= row <= rows and 1 <= seat <= seats_per_row):
            # Record the rejected booking before raising
            logger.error("Rejected booking on screening %s: seat %s-%s does not exist", screening_id, row, seat)
            # Raise the generic exception describing the missing seat
            raise ProcessingException("seat does not exist")
        # Identify the seat inside this screening
        key = (screening_id, row, seat)
        # Reject the booking when the seat is already held by a client
        if key in self._bookings:
            # Record the rejected booking before raising
            logger.error("Rejected booking on screening %s: seat %s-%s already booked", screening_id, row, seat)
            # Raise the generic exception describing the conflict
            raise ProcessingException("seat already booked")
        # Record the client as the holder of the seat
        self._bookings[key] = client_id

    # Lists every seat of a screening in row-major order, flagging whether each one is still available
    def get_seat_availability(self, screening_id):
        # Reject unknown screenings so callers cannot mistake them for empty rooms
        if screening_id not in self._rooms:
            # Record the rejected query before raising
            logger.error("Rejected availability query on screening %s: unknown screening", screening_id)
            # Raise the generic exception describing the unknown screening
            raise ProcessingException("unknown screening")
        # Read the layout of the room where the screening takes place
        rows, seats_per_row = self._rooms[screening_id]
        # Accumulate one entry per seat of the room
        availability = []
        # Walk every row of the room
        for row in range(1, rows + 1):
            # Walk every seat of the current row
            for seat in range(1, seats_per_row + 1):
                # Describe the seat and whether it is still free
                availability.append({"row": row, "seat": seat, "available": (screening_id, row, seat) not in self._bookings})
        # Return the full availability listing
        return availability
