# Standard library logging, used to record every booking outcome and every failure
import logging

# Logger shared by the whole module so all failures are logged through the same channel
logger = logging.getLogger(__name__)


# Generic exception raised at the service boundary so callers never see lower-level details
class ProcessingException(Exception):
    # Empty body: the class only carries a message supplied at raise time
    pass


# Service that tracks the room layout of each screening and the seats booked for it
class SeatBookingManager:
    # Creates a manager with no screenings registered yet
    def __init__(self):
        # Maps each screening id to its room layout and its bookings
        self._screenings = {}

    # Registers a screening together with the room it takes place in
    def register_screening(self, screening_id, rows, seats_per_row):
        # Store the room layout with an empty booking map for this screening
        self._screenings[screening_id] = {"rows": rows, "seats": seats_per_row, "bookings": {}}
        # Record the registration of the screening
        logger.info("Registered screening %s with %s rows of %s seats", screening_id, rows, seats_per_row)

    # Books one seat of a screening for a client, rejecting unknown screenings, seats outside the room and taken seats
    def book_seat(self, screening_id, row, seat, client_id):
        # Guard the whole booking so every failure is logged and wrapped at this boundary
        try:
            # Look up the screening by its id, or None when it was never registered
            screening = self._screenings.get(screening_id)
            # Check that the screening exists
            if screening is None:
                # Reject the booking because the screening is unknown
                raise ValueError("unknown screening")
            # Check that the requested seat lies inside the room
            if not (1 <= row <= screening["rows"] and 1 <= seat <= screening["seats"]):
                # Reject the booking because the seat is outside the room
                raise ValueError("seat outside the room")
            # Check whether the seat is already held by another booking
            if (row, seat) in screening["bookings"]:
                # Reject the booking because the seat is already booked
                raise ValueError("seat already booked")
            # Record the client as the holder of this seat
            screening["bookings"][(row, seat)] = client_id
            # Record the successful booking
            logger.info("Booked seat (%s, %s) of screening %s for client %s", row, seat, screening_id, client_id)
        # Catch any failure raised while booking
        except Exception as exception:
            # Log the failure with the seat it concerns before passing it on
            logger.error("Booking failed for screening %s seat (%s, %s): %s", screening_id, row, seat, exception)
            # Wrap the failure in the generic exception so callers see only the service boundary
            raise ProcessingException(f"Could not book seat: {exception}")

    # Lists every seat of a screening together with whether it is still available
    def get_seat_availability(self, screening_id):
        # Guard the lookup so every failure is logged and wrapped at this boundary
        try:
            # Look up the screening by its id, or None when it was never registered
            screening = self._screenings.get(screening_id)
            # Check that the screening exists
            if screening is None:
                # Reject the request because the screening is unknown
                raise ValueError("unknown screening")
            # Start with an empty list that will hold one entry per seat
            availability = []
            # Walk through every row of the room
            for row in range(1, screening["rows"] + 1):
                # Walk through every seat of the current row
                for seat in range(1, screening["seats"] + 1):
                    # Describe this seat and whether it is still free
                    availability.append({"row": row, "seat": seat, "available": (row, seat) not in screening["bookings"]})
            # Return the availability of every seat of the screening
            return availability
        # Catch any failure raised while reading the availability
        except Exception as exception:
            # Log the failure with the screening it concerns before passing it on
            logger.error("Availability lookup failed for screening %s: %s", screening_id, exception)
            # Wrap the failure in the generic exception so callers see only the service boundary
            raise ProcessingException(f"Could not read availability: {exception}")
