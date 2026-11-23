# Import the standard logging module so every layer can record the exceptions it passes through.
import logging

# Module-level logger shared by the service layer.
logger = logging.getLogger(__name__)


# Generic exception raised at the service boundary so implementation details do not leak to clients.
class ProcessingException(Exception):
    # Empty body: the message passed to the constructor is the only payload.
    pass


# Physical layout of a room: a grid of numbered rows and numbered seats per row.
class Room:
    # Stores the layout of the room.
    def __init__(self, rows, seats_per_row):
        # Number of rows in the room.
        self.rows = rows
        # Number of seats in each row.
        self.seats_per_row = seats_per_row

    # Tells whether the given (row, seat) pair exists in this room; rows and seats are numbered from 1.
    def is_valid_seat(self, row, seat):
        # True when the row is within 1..rows and the seat is within 1..seats_per_row.
        return 1 <= row <= self.rows and 1 <= seat <= self.seats_per_row


# Service that registers screenings, books seats for clients and exposes seat availability.
class ScreeningManager:
    # Creates the manager with no screenings and no bookings.
    def __init__(self):
        # Room in which each screening takes place, keyed by screening id.
        self._rooms = {}
        # Bookings per screening: {screening_id: {(row, seat): client_id}}.
        self._bookings = {}

    # Registers a screening and the room where it takes place.
    def add_screening(self, screening_id, room):
        # Remember the room of the screening.
        self._rooms[screening_id] = room
        # Start the screening with no seat booked.
        self._bookings[screening_id] = {}

    # Books the given seat of a screening for a client; rejects unknown screenings, invalid seats and seats already booked.
    def book_seat(self, screening_id, client_id, row, seat):
        # Start of the block whose failures are logged and wrapped.
        try:
            # Reject a screening that was never registered.
            if screening_id not in self._rooms:
                # Raise a domain error that the except block below handles.
                raise ValueError("unknown screening: %s" % screening_id)
            # Look up the room in which the screening takes place.
            room = self._rooms[screening_id]
            # Reject a seat that does not exist in that room.
            if not room.is_valid_seat(row, seat):
                # Raise a domain error that the except block below handles.
                raise ValueError("invalid seat: row %s, seat %s" % (row, seat))
            # Look up the bookings already recorded for the screening.
            bookings = self._bookings[screening_id]
            # Reject a seat that is already booked.
            if (row, seat) in bookings:
                # Raise a domain error that the except block below handles.
                raise ValueError("seat already booked: row %s, seat %s" % (row, seat))
            # Record the client as the owner of the seat.
            bookings[(row, seat)] = client_id
        # Catch the domain errors raised above.
        except ValueError as error:
            # Log the failure before rethrowing it.
            logger.error("book_seat failed: %s", error)
            # Wrap the failure in the generic exception of the service boundary.
            raise ProcessingException("seat booking rejected")

    # Returns the availability of every seat of a screening as a list of {row, seat, available} entries.
    def get_seat_availability(self, screening_id):
        # Start of the block whose failures are logged and wrapped.
        try:
            # Reject a screening that was never registered.
            if screening_id not in self._rooms:
                # Raise a domain error that the except block below handles.
                raise ValueError("unknown screening: %s" % screening_id)
            # Look up the room in which the screening takes place.
            room = self._rooms[screening_id]
            # Look up the bookings recorded for the screening.
            bookings = self._bookings[screening_id]
            # Collect one availability entry per seat of the room.
            availability = []
            # Walk every row of the room in order.
            for row in range(1, room.rows + 1):
                # Walk every seat of the current row in order.
                for seat in range(1, room.seats_per_row + 1):
                    # Record whether the seat is free, i.e. not present in the bookings.
                    availability.append({"row": row, "seat": seat, "available": (row, seat) not in bookings})
            # Hand the full availability list back to the caller.
            return availability
        # Catch the domain errors raised above.
        except ValueError as error:
            # Log the failure before rethrowing it.
            logger.error("get_seat_availability failed: %s", error)
            # Wrap the failure in the generic exception of the service boundary.
            raise ProcessingException("seat availability unavailable")
