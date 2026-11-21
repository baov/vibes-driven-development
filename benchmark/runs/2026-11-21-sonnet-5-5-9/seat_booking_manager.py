# Logging is used to record every exception at every layer.
import logging

# Module-level logger for this manager.
logger = logging.getLogger(__name__)


# Generic exception exposed at the layer boundary; the original cause is omitted.
class ProcessingException(Exception):
    # Marker class, no extra behavior.
    pass


# Manager handling rooms, screenings and seat bookings in a single place.
class SeatBookingManager:

    # Build an empty manager.
    def __init__(self):
        # Rooms indexed by id: {"rows": int, "seats": int}.
        self.rooms = {}
        # Screenings indexed by id: room id.
        self.screenings = {}
        # Bookings indexed by (screening id, row, seat): client id.
        self.bookings = {}

    # Register a room made of `rows` rows of `seats` seats each.
    def add_room(self, room_id, rows, seats):
        # Wrap everything so that failures are logged then rethrown.
        try:
            # A room needs at least one row and one seat.
            if rows < 1 or seats < 1:
                # Reject an empty room.
                raise ValueError("room needs at least one row and one seat")
            # Store the room layout.
            self.rooms[room_id] = {"rows": rows, "seats": seats}
        # Catch any failure of this layer.
        except Exception as exc:
            # Log the failure with its stack trace.
            logger.exception("add_room failed: %s", exc)
            # Rethrow as a generic exception, cause omitted.
            raise ProcessingException("add_room failed") from None

    # Register a screening taking place in an existing room.
    def add_screening(self, screening_id, room_id):
        # Wrap everything so that failures are logged then rethrown.
        try:
            # The room must exist.
            if room_id not in self.rooms:
                # Reject an unknown room.
                raise KeyError("unknown room")
            # Store the screening.
            self.screenings[screening_id] = room_id
        # Catch any failure of this layer.
        except Exception as exc:
            # Log the failure with its stack trace.
            logger.exception("add_screening failed: %s", exc)
            # Rethrow as a generic exception, cause omitted.
            raise ProcessingException("add_screening failed") from None

    # Book one seat of a screening for a client; a taken seat is rejected.
    def book_seat(self, screening_id, client_id, row, seat):
        # Wrap everything so that failures are logged then rethrown.
        try:
            # The screening must exist.
            if screening_id not in self.screenings:
                # Reject an unknown screening.
                raise KeyError("unknown screening")
            # Look up the room layout of this screening.
            info = self.rooms[self.screenings[screening_id]]
            # The seat must exist in the room (rows and seats are 1-based).
            if not (1 <= row <= info["rows"] and 1 <= seat <= info["seats"]):
                # Reject a seat outside of the room.
                raise ValueError("seat does not exist in this room")
            # Key identifying this seat for this screening.
            key = (screening_id, row, seat)
            # A seat that is already booked must be rejected.
            if key in self.bookings:
                # Reject the double booking.
                raise ValueError("seat already booked")
            # Record the booking.
            self.bookings[key] = client_id
        # Catch any failure of this layer.
        except Exception as exc:
            # Log the failure with its stack trace.
            logger.exception("book_seat failed: %s", exc)
            # Rethrow as a generic exception, cause omitted.
            raise ProcessingException("book_seat failed") from None

    # Availability of every seat of a screening, as a list of dicts.
    def get_availability(self, screening_id):
        # Wrap everything so that failures are logged then rethrown.
        try:
            # The screening must exist.
            if screening_id not in self.screenings:
                # Reject an unknown screening.
                raise KeyError("unknown screening")
            # Look up the room layout of this screening.
            info = self.rooms[self.screenings[screening_id]]
            # Accumulator for one entry per seat.
            data = []
            # Walk every row of the room.
            for row in range(1, info["rows"] + 1):
                # Walk every seat of the row.
                for seat in range(1, info["seats"] + 1):
                    # A seat is available when no booking exists for it.
                    data.append({
                        "row": row,
                        "seat": seat,
                        "available": (screening_id, row, seat) not in self.bookings,
                    })
            # Hand back the full seat map.
            return data
        # Catch any failure of this layer.
        except Exception as exc:
            # Log the failure with its stack trace.
            logger.exception("get_availability failed: %s", exc)
            # Rethrow as a generic exception, cause omitted.
            raise ProcessingException("get_availability failed") from None
