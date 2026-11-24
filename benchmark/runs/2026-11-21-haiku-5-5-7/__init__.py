# Import the logging module so every layer can report the exceptions it passes through.
import logging
# Import the threading module so the check-then-write of a booking happens atomically.
import threading

# Create a logger named after this module so log lines show where they came from.
logger = logging.getLogger(__name__)


# Declare the generic exception that layer boundaries raise to hide implementation details.
class ProcessingException(Exception):
    # Empty body: the class exists so callers can catch any processing failure by one type.
    pass


# Declare the exception raised when a client asks for a seat that is already booked.
class SeatAlreadyBookedException(ProcessingException):
    # Empty body: the subclass only gives the already-booked rejection its own type.
    pass


# Declare the in-memory store that holds screenings, their rooms and their bookings.
class SeatStoreHelper:
    # Start the store with no rooms and no bookings.
    def __init__(self):
        # Map each screening id to its (rows, seats_per_row) room dimensions.
        self._rooms = {}
        # Map each screening id to its bookings, keyed by (row, seat) with the client id as value.
        self._bookings = {}

    # Record a screening's room and start it with no bookings.
    def save_screening(self, screening_id, rows, seats_per_row):
        # Store the room dimensions under the screening id.
        self._rooms[screening_id] = (rows, seats_per_row)
        # Create an empty booking map for the screening.
        self._bookings[screening_id] = {}

    # Return the room dimensions of a screening, or None when the screening is unknown.
    def find_room(self, screening_id):
        # Look the room up without raising when the screening id is missing.
        return self._rooms.get(screening_id)

    # Return a copy of the bookings of a screening so callers cannot change the stored state.
    def list_bookings(self, screening_id):
        # Copy the booking map before handing it back.
        return dict(self._bookings[screening_id])

    # Record that a client holds a seat for a screening.
    def save_booking(self, screening_id, row, seat, client_id):
        # Store the client id against the (row, seat) key of the screening.
        self._bookings[screening_id][(row, seat)] = client_id


# Declare the manager that validates seat booking requests and enforces one client per seat.
class SeatBookingManager:
    # Wire the manager to a store, creating an in-memory store when none is injected.
    def __init__(self, store=None):
        # Use the injected store, or create a fresh in-memory one.
        self._store = store if store is not None else SeatStoreHelper()
        # Create the lock that serializes bookings so two clients cannot take the same seat.
        self._lock = threading.Lock()

    # Register a screening in a room with the given number of rows and seats per row.
    def add_screening(self, screening_id, rows, seats_per_row):
        # Open the layer boundary so every failure is logged before it leaves the manager.
        try:
            # Reject room dimensions that are not positive integers.
            if not (isinstance(rows, int) and rows > 0 and isinstance(seats_per_row, int) and seats_per_row > 0):
                # Raise a processing failure describing the invalid dimensions.
                raise ProcessingException(f"invalid room dimensions for screening {screening_id}")
            # Save the screening through the store.
            self._store.save_screening(screening_id, rows, seats_per_row)
        # Log and re-raise processing failures unchanged.
        except ProcessingException as exception:
            # Log the rejection with its message.
            logger.error("add_screening rejected: %s", exception)
            # Re-raise the same exception to the caller.
            raise
        # Log and wrap any unexpected failure so implementation details do not leak.
        except Exception:
            # Log the traceback of the unexpected failure.
            logger.exception("add_screening failed for screening %s", screening_id)
            # Raise the generic processing failure in place of the original error.
            raise ProcessingException(f"could not add screening {screening_id}")

    # Book a seat for a client, rejecting unknown screenings, nonexistent seats and seats already taken.
    def book_seat(self, screening_id, row, seat, client_id):
        # Hold the lock across the check and the write so concurrent requests cannot both succeed.
        with self._lock:
            # Open the layer boundary so every failure is logged before it leaves the manager.
            try:
                # Fetch the room so the requested seat can be checked against it.
                room = self._store.find_room(screening_id)
                # Reject bookings for screenings that do not exist.
                if room is None:
                    # Raise a processing failure naming the unknown screening.
                    raise ProcessingException(f"unknown screening {screening_id}")
                # Split the room dimensions into rows and seats per row.
                rows, seats_per_row = room
                # Reject seats outside the room, numbering rows and seats from 1.
                if not (isinstance(row, int) and 1 <= row <= rows and isinstance(seat, int) and 1 <= seat <= seats_per_row):
                    # Raise a processing failure naming the nonexistent seat.
                    raise ProcessingException(f"seat {row}-{seat} does not exist in screening {screening_id}")
                # Reject the request when the seat is already held by a client.
                if (row, seat) in self._store.list_bookings(screening_id):
                    # Raise the dedicated rejection so callers can tell a taken seat apart.
                    raise SeatAlreadyBookedException(f"seat {row}-{seat} is already booked for screening {screening_id}")
                # Record the booking for the client.
                self._store.save_booking(screening_id, row, seat, client_id)
            # Log and re-raise processing failures unchanged.
            except ProcessingException as exception:
                # Log the rejection with its message.
                logger.error("book_seat rejected: %s", exception)
                # Re-raise the same exception to the caller.
                raise
            # Log and wrap any unexpected failure so implementation details do not leak.
            except Exception:
                # Log the traceback of the unexpected failure.
                logger.exception("book_seat failed for screening %s", screening_id)
                # Raise the generic processing failure in place of the original error.
                raise ProcessingException(f"could not book seat {row}-{seat} for screening {screening_id}")

    # Return the availability of every seat of a screening as {(row, seat): is_available}.
    def get_seat_availability(self, screening_id):
        # Open the layer boundary so every failure is logged before it leaves the manager.
        try:
            # Fetch the room so every seat of the screening can be listed.
            room = self._store.find_room(screening_id)
            # Reject queries for screenings that do not exist.
            if room is None:
                # Raise a processing failure naming the unknown screening.
                raise ProcessingException(f"unknown screening {screening_id}")
            # Split the room dimensions into rows and seats per row.
            rows, seats_per_row = room
            # Read the current bookings once so every seat is judged against the same snapshot.
            bookings = self._store.list_bookings(screening_id)
            # Start an empty availability map.
            availability = {}
            # Walk every row of the room, numbering rows from 1.
            for row in range(1, rows + 1):
                # Walk every seat of the row, numbering seats from 1.
                for seat in range(1, seats_per_row + 1):
                    # A seat is available when no client is recorded against it.
                    availability[(row, seat)] = (row, seat) not in bookings
            # Hand back the completed availability map.
            return availability
        # Log and re-raise processing failures unchanged.
        except ProcessingException as exception:
            # Log the rejection with its message.
            logger.error("get_seat_availability rejected: %s", exception)
            # Re-raise the same exception to the caller.
            raise
        # Log and wrap any unexpected failure so implementation details do not leak.
        except Exception:
            # Log the traceback of the unexpected failure.
            logger.exception("get_seat_availability failed for screening %s", screening_id)
            # Raise the generic processing failure in place of the original error.
            raise ProcessingException(f"could not read seat availability for screening {screening_id}")
