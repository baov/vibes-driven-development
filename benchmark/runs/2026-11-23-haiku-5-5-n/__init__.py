# Import the standard logging module to record booking failures.
import logging

# Create the module logger used by the booking layer.
logger = logging.getLogger(__name__)


# Generic exception that the booking layer raises for any rejected operation.
class ProcessingException(Exception):
    # Carries only the message given at raise time.
    pass


# Raised when a client tries to book a seat that is already booked.
class SeatAlreadyBookedException(ProcessingException):
    # Carries only the message given at raise time.
    pass


# Value object describing the rows and seats of a screening room.
class Room:

    # Creates a room with a fixed number of rows and seats per row.
    def __init__(self, rows, seats_per_row):
        # Reject a room that cannot hold any seat.
        if rows < 1 or seats_per_row < 1:
            # Raise an error describing the invalid size.
            raise ValueError("a room needs at least one row and one seat per row")
        # Store the number of rows.
        self.rows = rows
        # Store the number of seats per row.
        self.seats_per_row = seats_per_row

    # Tells whether the given row and seat number exist in this room.
    def has_seat(self, row, seat):
        # Rows and seats are numbered from 1 up to the room size.
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row

    # Lists every (row, seat) position of the room.
    def seats(self):
        # Build all positions, row by row, numbered from 1.
        return [(row, seat) for row in range(1, self.rows + 1) for seat in range(1, self.seats_per_row + 1)]


# Coordinates screenings, their rooms and the seat bookings made on them.
class SeatBookingManager:

    # Starts with no screenings and no bookings.
    def __init__(self):
        # Map each screening identifier to the room where it takes place.
        self._rooms = {}
        # Map (screening, row, seat) to the identifier of the client holding that seat.
        self._bookings = {}

    # Registers a screening taking place in the given room.
    def add_screening(self, screening_id, room):
        # Remember the room of this screening.
        self._rooms[screening_id] = room

    # Books a seat of a screening for a client, rejecting seats that are already booked.
    def book_seat(self, screening_id, row, seat, client_id):
        # Run the booking inside a try block so that failures are logged before they propagate.
        try:
            # Reject the booking if the screening is unknown.
            if screening_id not in self._rooms:
                # Raise a generic processing error naming the screening.
                raise ProcessingException("unknown screening: %s" % screening_id)
            # Fetch the room where the screening takes place.
            room = self._rooms[screening_id]
            # Reject the booking if the room has no such seat.
            if not room.has_seat(row, seat):
                # Raise a generic processing error naming the seat.
                raise ProcessingException("unknown seat %s-%s in screening %s" % (row, seat, screening_id))
            # Build the key identifying this seat of this screening.
            key = (screening_id, row, seat)
            # Reject the booking if the seat is already held.
            if key in self._bookings:
                # Raise the dedicated error for a seat that is already booked.
                raise SeatAlreadyBookedException("seat %s-%s of screening %s is already booked" % (row, seat, screening_id))
            # Record the client as the holder of the seat.
            self._bookings[key] = client_id
        # Catch processing failures to log them at this layer.
        except ProcessingException as error:
            # Log the failure with its message.
            logger.error("booking rejected: %s", error)
            # Rethrow the same failure to the caller.
            raise

    # Returns the availability of every seat of a screening, keyed by (row, seat).
    def seat_availability(self, screening_id):
        # Run the lookup inside a try block so that failures are logged before they propagate.
        try:
            # Reject the lookup if the screening is unknown.
            if screening_id not in self._rooms:
                # Raise a generic processing error naming the screening.
                raise ProcessingException("unknown screening: %s" % screening_id)
            # Fetch the room where the screening takes place.
            room = self._rooms[screening_id]
            # Mark each seat as available when no booking exists for it.
            return {(row, seat): (screening_id, row, seat) not in self._bookings for row, seat in room.seats()}
        # Catch processing failures to log them at this layer.
        except ProcessingException as error:
            # Log the failure with its message.
            logger.error("availability lookup rejected: %s", error)
            # Rethrow the same failure to the caller.
            raise
