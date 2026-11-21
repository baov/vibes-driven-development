# Logging is used to record every exception at each layer it passes through
import logging
# A lock makes the check-then-book sequence atomic across threads
import threading

# Module-level logger for this package
logger = logging.getLogger(__name__)


# Generic exception raised at layer boundaries
class ProcessingException(Exception):
    # Marker class: no extra behaviour needed
    pass


# Raised when a seat is booked twice (still a ProcessingException for callers)
class SeatAlreadyBookedException(ProcessingException):
    # Marker class: no extra behaviour needed
    pass


# Holds rooms, screenings and bookings, and exposes booking and availability
class SeatBookingManager:
    # Create an empty manager
    def __init__(self):
        # Maps room id to a (rows, seats_per_row) tuple
        self.rooms = {}
        # Maps screening id to its room id
        self.screenings = {}
        # Maps screening id to a dict of (row, seat) -> client id
        self.bookings = {}
        # Guards all mutations of bookings
        self.lock = threading.Lock()

    # Register a room made of `rows` rows, each with `seats_per_row` seats
    def add_room(self, room_id, rows, seats_per_row):
        # Log and rethrow any failure, wrapped in ProcessingException
        try:
            # A room needs at least one row and one seat
            if rows < 1 or seats_per_row < 1:
                # Reject invalid dimensions
                raise ValueError("a room needs at least one row and one seat")
            # Refuse to silently overwrite an existing room
            if room_id in self.rooms:
                # Reject duplicate room ids
                raise ValueError("room already exists: %s" % room_id)
            # Store the room dimensions
            self.rooms[room_id] = (rows, seats_per_row)
        # Catch anything raised above
        except Exception as exc:
            # Record the failure at this layer
            logger.exception("add_room failed")
            # Wrap in the generic exception, keeping the cause for debugging
            raise ProcessingException("add_room failed: %s" % exc) from exc

    # Register a screening that takes place in an existing room
    def add_screening(self, screening_id, room_id):
        # Log and rethrow any failure, wrapped in ProcessingException
        try:
            # The room must exist
            if room_id not in self.rooms:
                # Reject unknown rooms
                raise ValueError("unknown room: %s" % room_id)
            # Refuse to silently overwrite an existing screening
            if screening_id in self.screenings:
                # Reject duplicate screening ids
                raise ValueError("screening already exists: %s" % screening_id)
            # Link the screening to its room
            self.screenings[screening_id] = room_id
            # Start with no booked seat
            self.bookings[screening_id] = {}
        # Catch anything raised above
        except Exception as exc:
            # Record the failure at this layer
            logger.exception("add_screening failed")
            # Wrap in the generic exception, keeping the cause for debugging
            raise ProcessingException("add_screening failed: %s" % exc) from exc

    # Book seat number `seat` of row `row` (both 1-based) for a client
    def book_seat(self, screening_id, client_id, row, seat):
        # Log and rethrow any failure
        try:
            # Make the check and the write one atomic step
            with self.lock:
                # The screening must exist
                if screening_id not in self.screenings:
                    # Reject unknown screenings
                    raise ValueError("unknown screening: %s" % screening_id)
                # Look up the room dimensions for this screening
                rows, seats_per_row = self.rooms[self.screenings[screening_id]]
                # The seat must exist in the room
                if not (1 <= row <= rows and 1 <= seat <= seats_per_row):
                    # Reject seats outside the room
                    raise ValueError("no such seat: row %s seat %s" % (row, seat))
                # Seats already booked for this screening
                booked = self.bookings[screening_id]
                # A seat can only be booked once
                if (row, seat) in booked:
                    # Reject the double booking
                    raise SeatAlreadyBookedException(
                        "seat already booked: row %s seat %s" % (row, seat))
                # Record who holds the seat
                booked[(row, seat)] = client_id
        # Let the booking rejection keep its specific type
        except SeatAlreadyBookedException:
            # Record the failure at this layer
            logger.exception("book_seat rejected")
            # Rethrow unchanged
            raise
        # Catch any other failure
        except Exception as exc:
            # Record the failure at this layer
            logger.exception("book_seat failed")
            # Wrap in the generic exception, keeping the cause for debugging
            raise ProcessingException("book_seat failed: %s" % exc) from exc

    # Return availability of every seat of a screening
    def get_seat_availability(self, screening_id):
        # Log and rethrow any failure, wrapped in ProcessingException
        try:
            # Read a consistent snapshot
            with self.lock:
                # The screening must exist
                if screening_id not in self.screenings:
                    # Reject unknown screenings
                    raise ValueError("unknown screening: %s" % screening_id)
                # Look up the room dimensions for this screening
                rows, seats_per_row = self.rooms[self.screenings[screening_id]]
                # Seats already booked for this screening
                booked = self.bookings[screening_id]
                # One entry per seat, True when still free
                return {
                    (row, seat): (row, seat) not in booked
                    for row in range(1, rows + 1)
                    for seat in range(1, seats_per_row + 1)
                }
        # Catch anything raised above
        except Exception as exc:
            # Record the failure at this layer
            logger.exception("get_seat_availability failed")
            # Wrap in the generic exception, keeping the cause for debugging
            raise ProcessingException(
                "get_seat_availability failed: %s" % exc) from exc
