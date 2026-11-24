# Standard library module that records the exceptions passing through each layer
import logging
# Standard library module providing a lock so a check-then-book step is atomic
import threading

# Logger that records every exception the booking service lets through
logger = logging.getLogger(__name__)


# Generic exception that hides implementation details from callers of the service
class ProcessingException(Exception):
    # Marks a failed operation without exposing the underlying cause
    pass


# Raised when a client tries to book a seat that is already taken
class SeatAlreadyBookedException(ProcessingException):
    # Marks a rejected booking; it is a ProcessingException so callers can catch either
    pass


# Service that keeps screenings, their room layouts and their seat bookings in memory
class SeatBookingManager:
    # Creates a service with no screenings and no bookings
    def __init__(self):
        # Maps each screening id to its room size and to the seats booked so far
        self._screenings = {}
        # Lock that makes the check-then-book step atomic across client threads
        self._lock = threading.Lock()

    # Registers a screening that takes place in a room with the given rows and seats per row
    def add_screening(self, screening_id, rows, seats_per_row):
        # Start the guarded block that observes every failure of this method
        try:
            # Reject a room that does not have at least one row and one seat
            if rows < 1 or seats_per_row < 1:
                # Raise the generic exception for an invalid room size
                raise ProcessingException("A room needs at least one row and one seat")
            # Take the lock while the screenings map is modified
            with self._lock:
                # Store the room size together with an empty set of bookings
                self._screenings[screening_id] = {"rows": rows, "seats_per_row": seats_per_row, "bookings": {}}
        # Handle failures that the service raised on purpose
        except ProcessingException:
            # Log the rejected screening before passing the exception on
            logger.exception("Could not add screening %s", screening_id)
            # Rethrow the same exception to the caller
            raise
        # Handle unexpected failures, such as sizes that are not numbers
        except Exception:
            # Log the unexpected failure before wrapping it
            logger.exception("Unexpected failure while adding screening %s", screening_id)
            # Wrap the failure so that no implementation details leak to the caller
            raise ProcessingException("Could not add screening")

    # Books one seat of a screening for a client, rejecting seats that are out of range or taken
    def book_seat(self, screening_id, row, seat, client_id):
        # Start the guarded block that observes every failure of this method
        try:
            # Take the lock so no other client can book between the check and the write
            with self._lock:
                # Look up the screening that the client wants to book a seat for
                screening = self._screenings.get(screening_id)
                # Reject a screening id that does not exist
                if screening is None:
                    # Raise the generic exception for an unknown screening
                    raise ProcessingException("Unknown screening")
                # Reject a seat outside the rows and seats of the room
                if not (1 <= row <= screening["rows"] and 1 <= seat <= screening["seats_per_row"]):
                    # Raise the generic exception for a seat outside the room
                    raise ProcessingException("Seat is outside the room")
                # Reject a seat that another client has already booked
                if (row, seat) in screening["bookings"]:
                    # Raise the rejection that tells the client the seat is taken
                    raise SeatAlreadyBookedException("Seat is already booked")
                # Record the booking against the client
                screening["bookings"][(row, seat)] = client_id
        # Handle failures that the service raised on purpose, including the already-booked rejection
        except ProcessingException:
            # Log the rejected booking before passing the exception on
            logger.exception("Could not book seat %s/%s for screening %s", row, seat, screening_id)
            # Rethrow the same exception to the caller
            raise
        # Handle unexpected failures, such as a row that is not a number
        except Exception:
            # Log the unexpected failure before wrapping it
            logger.exception("Unexpected failure while booking seat %s/%s for screening %s", row, seat, screening_id)
            # Wrap the failure so that no implementation details leak to the caller
            raise ProcessingException("Could not book seat")

    # Returns the availability of every seat of a screening, in row-major order
    def get_seat_availability(self, screening_id):
        # Start the guarded block that observes every failure of this method
        try:
            # Take the lock so the availability is read from a consistent snapshot
            with self._lock:
                # Look up the screening whose seats should be reported
                screening = self._screenings.get(screening_id)
                # Reject a screening id that does not exist
                if screening is None:
                    # Raise the generic exception for an unknown screening
                    raise ProcessingException("Unknown screening")
                # Start the list that will hold one entry per seat
                availability = []
                # Walk over every row of the room
                for row in range(1, screening["rows"] + 1):
                    # Walk over every seat of the current row
                    for seat in range(1, screening["seats_per_row"] + 1):
                        # Record whether this seat is free, i.e. not present in the bookings
                        availability.append({"row": row, "seat": seat, "available": (row, seat) not in screening["bookings"]})
            # Return the availability of all seats
            return availability
        # Handle failures that the service raised on purpose
        except ProcessingException:
            # Log the failed lookup before passing the exception on
            logger.exception("Could not read availability of screening %s", screening_id)
            # Rethrow the same exception to the caller
            raise
        # Handle unexpected failures, such as an id that cannot be used as a key
        except Exception:
            # Log the unexpected failure before wrapping it
            logger.exception("Unexpected failure while reading availability of screening %s", screening_id)
            # Wrap the failure so that no implementation details leak to the caller
            raise ProcessingException("Could not read seat availability")
