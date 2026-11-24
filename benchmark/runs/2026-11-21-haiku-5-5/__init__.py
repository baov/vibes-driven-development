# Import the standard logging module so every failure is recorded at this layer
import logging
# Create the module logger that reports the exceptions passing through the manager
logger = logging.getLogger(__name__)


# Declare the generic failure raised at the layer boundary so implementation details do not leak
class ProcessingException(Exception):
    # Carry the message only, no extra behavior is needed
    pass


# Manage screenings and the seats booked for them in the seat reservation service
class SeatBookingManager:
    # Start with no screenings and no bookings
    def __init__(self):
        # Map each screening id to its room layout as (rows, seats_per_row)
        self._screenings = {}
        # Map each booked (screening_id, row, seat) to the client who booked it
        self._bookings = {}

    # Register a screening that takes place in a room with the given rows and seats per row
    def add_screening(self, screening_id, rows, seats_per_row):
        # Start the guarded block so every failure is logged and wrapped at this layer
        try:
            # Reject a screening id that is already registered
            if screening_id in self._screenings:
                # Signal the duplicate with a descriptive error
                raise ValueError(f"screening {screening_id!r} already exists")
            # Reject a room that has no rows or no seats
            if rows < 1 or seats_per_row < 1:
                # Signal the invalid room size with a descriptive error
                raise ValueError("a room needs at least one row and one seat")
            # Store the room layout under the screening id
            self._screenings[screening_id] = (rows, seats_per_row)
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure with its traceback before passing it on
            logger.exception("add_screening failed for screening %r", screening_id)
            # Wrap the failure in the generic exception raised at the boundary
            raise ProcessingException(f"could not add screening: {error}")

    # Reserve one seat of a screening for a client, rejecting unknown, outside or already booked seats
    def book_seat(self, screening_id, row, seat, client_id):
        # Start the guarded block so every failure is logged and wrapped at this layer
        try:
            # Reject a screening that was never registered
            if screening_id not in self._screenings:
                # Signal the unknown screening with a descriptive error
                raise ValueError(f"unknown screening {screening_id!r}")
            # Read the room layout of the screening to validate the seat position
            rows, seats_per_row = self._screenings[screening_id]
            # Reject a seat position that lies outside the room
            if not (1 <= row <= rows and 1 <= seat <= seats_per_row):
                # Signal the out-of-room seat with a descriptive error
                raise ValueError(f"seat ({row}, {seat}) is outside the room")
            # Reject a seat that is already booked for this screening
            if (screening_id, row, seat) in self._bookings:
                # Signal the double booking with a descriptive error
                raise ValueError(f"seat ({row}, {seat}) is already booked")
            # Record the client as the holder of the seat
            self._bookings[(screening_id, row, seat)] = client_id
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure with its traceback before passing it on
            logger.exception("book_seat failed for screening %r", screening_id)
            # Wrap the failure in the generic exception raised at the boundary
            raise ProcessingException(f"could not book seat: {error}")

    # Report whether each seat of a screening is available, keyed by (row, seat), True meaning available
    def get_seat_availability(self, screening_id):
        # Start the guarded block so every failure is logged and wrapped at this layer
        try:
            # Reject a screening that was never registered
            if screening_id not in self._screenings:
                # Signal the unknown screening with a descriptive error
                raise ValueError(f"unknown screening {screening_id!r}")
            # Read the room layout of the screening to enumerate its seats
            rows, seats_per_row = self._screenings[screening_id]
            # Start with an empty availability map
            availability = {}
            # Visit every row of the room
            for row in range(1, rows + 1):
                # Visit every seat of the current row
                for seat in range(1, seats_per_row + 1):
                    # Record True when no booking exists for this seat
                    availability[(row, seat)] = (screening_id, row, seat) not in self._bookings
            # Return the availability of every seat
            return availability
        # Catch any failure raised inside the guarded block
        except Exception as error:
            # Log the failure with its traceback before passing it on
            logger.exception("get_seat_availability failed for screening %r", screening_id)
            # Wrap the failure in the generic exception raised at the boundary
            raise ProcessingException(f"could not read seat availability: {error}")
