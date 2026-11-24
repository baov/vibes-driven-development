# Standard library logging: every layer logs the exceptions that pass through it.
import logging
# Standard library threading: guards the check-then-book step against concurrent requests.
import threading

# Module logger, named after the package so log lines show where they were emitted.
logger = logging.getLogger(__name__)


# Generic exception used at every layer boundary so implementation details do not leak.
class ProcessingException(Exception):
    # Empty body: the exception type alone carries the meaning.
    pass


# Raised when a client tries to book a seat that already holds a booking.
class SeatAlreadyBookedException(ProcessingException):
    # Empty body: a distinct type lets callers handle double booking specifically.
    pass


# Value object describing the layout of a room: rows and seats per row, both numbered from 1.
class Room:
    # Stores the layout after checking that both dimensions are positive integers.
    def __init__(self, rows, seats_per_row):
        # Start of the boundary block: any failure is logged and rethrown.
        try:
            # Reject non-positive dimensions, which describe no seats at all.
            if rows < 1 or seats_per_row < 1:
                # Explain which invariant was violated.
                raise ProcessingException("A room needs at least one row and one seat per row")
            # Remember the number of rows.
            self._rows = rows
            # Remember the number of seats in each row.
            self._seats_per_row = seats_per_row
        # Handle the errors raised deliberately above.
        except ProcessingException:
            # Record the failure with its stack trace.
            logger.exception("Invalid room layout rows=%s seats_per_row=%s", rows, seats_per_row)
            # Pass the same error on to the caller.
            raise
        # Handle unexpected errors, such as non-numeric dimensions.
        except Exception:
            # Record the unexpected failure with its stack trace.
            logger.exception("Could not create room")
            # Hide the implementation detail behind the generic exception type.
            raise ProcessingException("Could not create room")

    # Tells whether the given row and seat number exist in this room.
    def contains(self, row, seat):
        # Start of the boundary block: any failure is logged and rethrown.
        try:
            # Both indices must fall inside the layout, counting from 1.
            return 1 <= row <= self._rows and 1 <= seat <= self._seats_per_row
        # Handle unexpected errors, such as non-numeric indices.
        except Exception:
            # Record the failure with its stack trace.
            logger.exception("Could not check seat row=%s seat=%s", row, seat)
            # Hide the implementation detail behind the generic exception type.
            raise ProcessingException("Could not check seat")

    # Lists every (row, seat) pair of the room, in row-major order.
    def seats(self):
        # Build one tuple per seat, looping over rows first and then seats within each row.
        return [(row, seat) for row in range(1, self._rows + 1) for seat in range(1, self._seats_per_row + 1)]


# A screening taking place in a room, holding the bookings made for it.
class Screening:
    # Stores the screening identity, its room and an empty booking map guarded by a lock.
    def __init__(self, screening_id, room):
        # Remember the identifier of this screening.
        self._screening_id = screening_id
        # Remember the room in which the screening takes place.
        self._room = room
        # Map each booked (row, seat) to the client who holds it.
        self._bookings = {}
        # Lock that makes the check-then-book step atomic.
        self._lock = threading.Lock()

    # Books the given seat for the given client, rejecting invalid or already booked seats.
    def book(self, row, seat, client_id):
        # Start of the boundary block: any failure is logged and rethrown.
        try:
            # Refuse seats that do not exist in the room.
            if not self._room.contains(row, seat):
                # Explain that the requested seat is outside the layout.
                raise ProcessingException("Seat does not exist in this room")
            # Make the availability check and the write one atomic step.
            with self._lock:
                # Refuse seats that are already held by a booking.
                if (row, seat) in self._bookings:
                    # Signal the double booking to the caller.
                    raise SeatAlreadyBookedException("Seat is already booked")
                # Record the client as the holder of this seat.
                self._bookings[(row, seat)] = client_id
        # Handle the errors raised deliberately above.
        except ProcessingException:
            # Record the failure with its stack trace, without client details.
            logger.exception("Could not book seat row=%s seat=%s for screening=%s", row, seat, self._screening_id)
            # Pass the same error on to the caller, keeping its concrete type.
            raise
        # Handle unexpected errors from the room or the lock.
        except Exception:
            # Record the unexpected failure with its stack trace.
            logger.exception("Could not book seat row=%s seat=%s for screening=%s", row, seat, self._screening_id)
            # Hide the implementation detail behind the generic exception type.
            raise ProcessingException("Could not book seat")

    # Reports the availability of every seat of the room for this screening.
    def availability(self):
        # Hold the lock so the snapshot is consistent with concurrent bookings.
        with self._lock:
            # Build one entry per seat, marking it unavailable when a booking holds it.
            return [
                {"row": row, "seat": seat, "available": (row, seat) not in self._bookings}
                for row, seat in self._room.seats()
            ]


# Service entry point: keeps the registry of screenings and routes booking requests to them.
class SeatBookingManager:
    # Starts with no screenings registered.
    def __init__(self):
        # Map each screening identifier to its Screening object.
        self._screenings = {}

    # Registers a new screening taking place in the given room.
    def create_screening(self, screening_id, room):
        # Start of the boundary block: any failure is logged and rethrown.
        try:
            # Refuse to replace an existing screening.
            if screening_id in self._screenings:
                # Explain that the identifier is already in use.
                raise ProcessingException("Screening already exists")
            # Register the new screening under its identifier.
            self._screenings[screening_id] = Screening(screening_id, room)
        # Handle the errors raised deliberately above.
        except ProcessingException:
            # Record the failure with its stack trace.
            logger.exception("Could not create screening=%s", screening_id)
            # Pass the same error on to the caller.
            raise
        # Handle unexpected errors, such as unhashable identifiers.
        except Exception:
            # Record the unexpected failure with its stack trace.
            logger.exception("Could not create screening=%s", screening_id)
            # Hide the implementation detail behind the generic exception type.
            raise ProcessingException("Could not create screening")

    # Books a seat for a client in the given screening.
    def book_seat(self, screening_id, row, seat, client_id):
        # Start of the boundary block: any failure is logged and rethrown.
        try:
            # Look up the requested screening.
            screening = self._screenings.get(screening_id)
            # Refuse requests for screenings that were never registered.
            if screening is None:
                # Explain that the screening is unknown.
                raise ProcessingException("Unknown screening")
            # Delegate the booking, which rejects double bookings itself.
            screening.book(row, seat, client_id)
        # Handle the errors raised deliberately above, including double bookings.
        except ProcessingException:
            # Record the failure with its stack trace.
            logger.exception("Could not book seat row=%s seat=%s for screening=%s", row, seat, screening_id)
            # Pass the same error, with its concrete type, on to the caller.
            raise
        # Handle unexpected errors from the screening.
        except Exception:
            # Record the unexpected failure with its stack trace.
            logger.exception("Could not book seat row=%s seat=%s for screening=%s", row, seat, screening_id)
            # Hide the implementation detail behind the generic exception type.
            raise ProcessingException("Could not book seat")

    # Returns the availability of every seat of the given screening.
    def get_seat_availability(self, screening_id):
        # Start of the boundary block: any failure is logged and rethrown.
        try:
            # Look up the requested screening.
            screening = self._screenings.get(screening_id)
            # Refuse requests for screenings that were never registered.
            if screening is None:
                # Explain that the screening is unknown.
                raise ProcessingException("Unknown screening")
            # Return the per-seat availability computed by the screening.
            return screening.availability()
        # Handle the errors raised deliberately above.
        except ProcessingException:
            # Record the failure with its stack trace.
            logger.exception("Could not read availability for screening=%s", screening_id)
            # Pass the same error on to the caller.
            raise
        # Handle unexpected errors from the screening.
        except Exception:
            # Record the unexpected failure with its stack trace.
            logger.exception("Could not read availability for screening=%s", screening_id)
            # Hide the implementation detail behind the generic exception type.
            raise ProcessingException("Could not read availability")
