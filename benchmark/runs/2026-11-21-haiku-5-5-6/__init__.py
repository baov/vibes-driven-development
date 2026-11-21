# Import logging so that every exception can be recorded at the layer where it passes through.
import logging

# Create the module logger that records the exceptions raised by SeatBookingManager.
_LOGGER = logging.getLogger(__name__)


# Define the generic exception that every rejected operation raises to its callers.
class ProcessingException(Exception):
    # Leave the body empty: the message given to the constructor is the only detail exposed.
    pass


# Define the manager that registers screenings and books their seats.
class SeatBookingManager:
    # Create a manager with no screenings registered yet.
    def __init__(self):
        # Hold the registered screenings keyed by screening id; each holds its room size and its bookings.
        self._screenings = {}

    # Register a screening held in a room of the given number of rows and seats per row.
    def add_screening(self, screening_id, rows, seats_per_row):
        # Start the guarded block so that every failure is logged before it leaves this method.
        try:
            # Reject a room with no row or no seat, since no seat could ever be booked in it.
            if rows < 1 or seats_per_row < 1:
                # Raise the generic exception describing the invalid room size.
                raise ProcessingException("room must have at least one row and one seat")
            # Reject a repeated id, because overwriting it would silently discard its bookings.
            if screening_id in self._screenings:
                # Raise the generic exception describing the duplicate screening.
                raise ProcessingException("screening already registered")
            # Store the room size together with an empty map of bookings.
            self._screenings[screening_id] = {"rows": rows, "seats_per_row": seats_per_row, "bookings": {}}
        # Handle the exceptions this method raised deliberately.
        except ProcessingException:
            # Log the rejected operation together with the screening it concerned.
            _LOGGER.exception("add_screening rejected for screening %s", screening_id)
            # Rethrow the same exception unchanged to the caller.
            raise
        # Handle unexpected exceptions from lower layers, such as a comparison between incompatible types.
        except Exception:
            # Log the unexpected failure together with its traceback.
            _LOGGER.exception("add_screening failed for screening %s", screening_id)
            # Wrap the failure in the generic exception, omitting the original cause to avoid leaking details.
            raise ProcessingException("invalid screening definition") from None

    # Book one seat of a screening for a client, rejecting seats that do not exist or are already booked.
    def book_seat(self, screening_id, row, seat, client_id):
        # Start the guarded block so that every failure is logged before it leaves this method.
        try:
            # Look up the screening; the result is None when the id was never registered.
            data = self._screenings.get(screening_id)
            # Reject the request when there is no such screening to book into.
            if data is None:
                # Raise the generic exception describing the unknown screening.
                raise ProcessingException("unknown screening")
            # Reject a seat outside the room, where rows and seats are numbered from 1.
            if not (1 <= row <= data["rows"] and 1 <= seat <= data["seats_per_row"]):
                # Raise the generic exception describing the nonexistent seat.
                raise ProcessingException("seat does not exist in this room")
            # Reject a seat that is already booked, so that no seat is sold twice.
            if (row, seat) in data["bookings"]:
                # Raise the generic exception describing the double booking.
                raise ProcessingException("seat already booked")
            # Record the client as the holder of the seat.
            data["bookings"][(row, seat)] = client_id
        # Handle the exceptions this method raised deliberately.
        except ProcessingException:
            # Log the rejected operation together with the screening it concerned.
            _LOGGER.exception("book_seat rejected for screening %s", screening_id)
            # Rethrow the same exception unchanged to the caller.
            raise
        # Handle unexpected exceptions from lower layers, such as a comparison between incompatible types.
        except Exception:
            # Log the unexpected failure together with its traceback.
            _LOGGER.exception("book_seat failed for screening %s", screening_id)
            # Wrap the failure in the generic exception, omitting the original cause to avoid leaking details.
            raise ProcessingException("invalid booking request") from None

    # Report whether every seat of a screening is available, keyed by (row, seat) with rows and seats numbered from 1.
    def get_seat_availability(self, screening_id):
        # Start the guarded block so that every failure is logged before it leaves this method.
        try:
            # Look up the screening; the result is None when the id was never registered.
            data = self._screenings.get(screening_id)
            # Reject the request when there is no such screening to report on.
            if data is None:
                # Raise the generic exception describing the unknown screening.
                raise ProcessingException("unknown screening")
            # Prepare the map that will hold one availability flag per seat.
            result = {}
            # Visit every row of the room in order.
            for row in range(1, data["rows"] + 1):
                # Visit every seat of the current row in order.
                for seat in range(1, data["seats_per_row"] + 1):
                    # Mark the seat as available when no booking exists for it.
                    result[(row, seat)] = (row, seat) not in data["bookings"]
            # Return the availability of every seat of the screening.
            return result
        # Handle the exceptions this method raised deliberately.
        except ProcessingException:
            # Log the rejected operation together with the screening it concerned.
            _LOGGER.exception("get_seat_availability rejected for screening %s", screening_id)
            # Rethrow the same exception unchanged to the caller.
            raise
        # Handle unexpected exceptions from lower layers, such as an unhashable screening id.
        except Exception:
            # Log the unexpected failure together with its traceback.
            _LOGGER.exception("get_seat_availability failed for screening %s", screening_id)
            # Wrap the failure in the generic exception, omitting the original cause to avoid leaking details.
            raise ProcessingException("invalid availability request") from None
