# Standard library logging, used to log every exception at every layer
import logging
# Standard library lock, so two concurrent bookings of one seat cannot both succeed
import threading

# Module-level logger shared by the service
LOGGER = logging.getLogger("seat_booking")


# Raised when a seat is already booked for the screening
class SeatAlreadyBookedException(Exception):
    # Plain exception, no extra behavior
    pass


# Raised when the screening id is not registered
class UnknownScreeningException(Exception):
    # Plain exception, no extra behavior
    pass


# Raised when the row/seat does not exist in the screening room
class InvalidSeatException(Exception):
    # Plain exception, no extra behavior
    pass


# Entity as plain data: a room has a number of rows and a number of seats per row
class Room:
    # Fields are set directly, no behavior
    def __init__(self, name, rows, seats_per_row):
        # Room name
        self.name = name
        # Number of rows (rows are numbered from 1)
        self.rows = rows
        # Number of seats in each row (seats are numbered from 1)
        self.seats_per_row = seats_per_row


# Entity as plain data: a screening takes place in a room
class Screening:
    # Fields are set directly, no behavior
    def __init__(self, screening_id, movie, room):
        # Screening identifier
        self.screening_id = screening_id
        # Movie title
        self.movie = movie
        # Room where the screening takes place
        self.room = room


# Service holding the booking business rules (role-based name, see AGENTS.md)
class SeatBookingManagerService:
    # Create an empty service
    def __init__(self):
        # Screenings by id
        self.screenings = {}
        # Bookings: screening id -> {(row, seat): client id}
        self.bookings = {}
        # Lock protecting the check-then-book sequence
        self.lock = threading.Lock()

    # Register a screening so seats can be booked for it
    def add_screening(self, screening):
        # Log and rethrow any failure
        try:
            # Make the check-and-store atomic
            with self.lock:
                # Store the screening under its id
                self.screenings[screening.screening_id] = screening
                # Start with no booking for it (keep existing bookings if re-registered)
                self.bookings.setdefault(screening.screening_id, {})
        # Observability: log at this layer
        except Exception:
            # Log with stack trace
            LOGGER.exception("add_screening failed")
            # Rethrow unchanged
            raise

    # Book one seat of a screening for a client; rejects an already booked seat
    def book_seat(self, screening_id, row, seat, client_id):
        # Log and rethrow any failure
        try:
            # Make the check-then-book sequence atomic
            with self.lock:
                # Look up the screening
                info = self.screenings.get(screening_id)
                # Unknown screening is rejected
                if info is None:
                    # Tell the caller which screening is unknown
                    raise UnknownScreeningException(screening_id)
                # Seat must exist in the room (rows and seats are numbered from 1)
                if not (1 <= row <= info.room.rows and 1 <= seat <= info.room.seats_per_row):
                    # Tell the caller which seat is invalid
                    raise InvalidSeatException((row, seat))
                # Bookings of this screening
                data = self.bookings[screening_id]
                # An already booked seat is rejected
                if (row, seat) in data:
                    # Tell the caller which seat is taken
                    raise SeatAlreadyBookedException((screening_id, row, seat))
                # Record the booking
                data[(row, seat)] = client_id
                # Return a plain description of the booking
                result = {"screening_id": screening_id, "row": row, "seat": seat, "client_id": client_id}
                # Hand it back
                return result
        # Observability: log at this layer
        except Exception:
            # Log with stack trace
            LOGGER.exception("book_seat failed")
            # Rethrow unchanged
            raise

    # Availability of every seat of a screening, ordered by row then seat
    def get_seat_availability(self, screening_id):
        # Log and rethrow any failure
        try:
            # Read a consistent snapshot
            with self.lock:
                # Look up the screening
                info = self.screenings.get(screening_id)
                # Unknown screening is rejected
                if info is None:
                    # Tell the caller which screening is unknown
                    raise UnknownScreeningException(screening_id)
                # Bookings of this screening
                data = self.bookings[screening_id]
                # One entry per seat of the room
                result = [
                    # A seat is available when nobody booked it
                    {"row": r, "seat": s, "available": (r, s) not in data}
                    # Every row of the room
                    for r in range(1, info.room.rows + 1)
                    # Every seat of the row
                    for s in range(1, info.room.seats_per_row + 1)
                ]
                # Hand it back
                return result
        # Observability: log at this layer
        except Exception:
            # Log with stack trace
            LOGGER.exception("get_seat_availability failed")
            # Rethrow unchanged
            raise
