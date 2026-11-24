# Import the standard logging module to record every rejected booking.
import logging
# Import the standard threading module to make the check-then-book step atomic.
import threading

# Create the module logger used by the manager to record rejections.
logger = logging.getLogger(__name__)


# Declare the generic exception the service raises so callers never see internal details.
class ProcessingException(Exception):
    # Keep the class body empty; the message carries the reason.
    pass


# Own rooms, screenings and seat bookings for cinema screenings, all held in memory.
class SeatBookingManager:
    # Create an empty manager with no rooms, screenings or bookings.
    def __init__(self):
        # Map each room id to a (rows, seats_per_row) tuple describing its layout.
        self._rooms = {}
        # Map each screening id to the id of the room where the screening takes place.
        self._screenings = {}
        # Map each (screening id, row, seat) to the client id that holds that seat.
        self._bookings = {}
        # Guard reads and writes of bookings so a seat cannot be booked twice concurrently.
        self._lock = threading.Lock()

    # Register a room with the given number of rows and seats per row.
    def add_room(self, room_id, rows, seats_per_row):
        # Store the room layout under its identifier.
        self._rooms[room_id] = (rows, seats_per_row)

    # Schedule a screening in a room that has already been registered.
    def add_screening(self, screening_id, room_id):
        # Reject the screening when its room was never registered.
        if room_id not in self._rooms:
            # Record the rejected request before raising.
            logger.error("Unknown room %s", room_id)
            # Raise the generic service exception with the reason.
            raise ProcessingException(f"Unknown room: {room_id}")
        # Attach the screening to its room.
        self._screenings[screening_id] = room_id

    # Book one seat of a screening for a client, rejecting unknown screenings, invalid seats and taken seats.
    def book_seat(self, screening_id, row, seat, client_id):
        # Hold the lock across the checks and the write so two clients cannot win the same seat.
        with self._lock:
            # Reject the booking when the screening does not exist.
            if screening_id not in self._screenings:
                # Record the rejected request before raising.
                logger.error("Unknown screening %s", screening_id)
                # Raise the generic service exception with the reason.
                raise ProcessingException(f"Unknown screening: {screening_id}")
            # Look up the layout of the room where this screening takes place.
            rows, seats_per_row = self._rooms[self._screenings[screening_id]]
            # Reject row or seat numbers outside the room, where numbering starts at 1.
            if not (1 <= row <= rows and 1 <= seat <= seats_per_row):
                # Record the rejected request before raising.
                logger.error("Seat %s-%s does not exist in screening %s", row, seat, screening_id)
                # Raise the generic service exception with the reason.
                raise ProcessingException(f"Seat {row}-{seat} does not exist")
            # Build the key that identifies this seat for this screening.
            key = (screening_id, row, seat)
            # Reject the booking when another client already holds this seat.
            if key in self._bookings:
                # Record the rejected request before raising.
                logger.error("Seat %s-%s already booked in screening %s", row, seat, screening_id)
                # Raise the generic service exception with the reason.
                raise ProcessingException(f"Seat {row}-{seat} is already booked")
            # Record the client as the holder of this seat.
            self._bookings[key] = client_id

    # Return a (row, seat, available) entry for every seat of a screening, ordered by row then seat.
    def get_seat_availability(self, screening_id):
        # Hold the lock so the availability is a consistent snapshot of the bookings.
        with self._lock:
            # Reject the request when the screening does not exist.
            if screening_id not in self._screenings:
                # Record the rejected request before raising.
                logger.error("Unknown screening %s", screening_id)
                # Raise the generic service exception with the reason.
                raise ProcessingException(f"Unknown screening: {screening_id}")
            # Look up the layout of the room where this screening takes place.
            rows, seats_per_row = self._rooms[self._screenings[screening_id]]
            # Build one entry per seat, marking it unavailable when a booking exists for it.
            return [
                # Emit the row, the seat and whether no booking exists for that seat.
                (row, seat, (screening_id, row, seat) not in self._bookings)
                # Iterate over every row, numbered from 1.
                for row in range(1, rows + 1)
                # Iterate over every seat in the row, numbered from 1.
                for seat in range(1, seats_per_row + 1)
            ]
