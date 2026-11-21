# Standard library logging, used to log every exception at every layer.
import logging


# Generic exception raised at the layer boundary, hiding lower-level details.
class ProcessingException(Exception):
    # Marker class only: the message is the whole payload.
    pass


# Service holding all seat booking behavior (rooms, screenings, bookings).
class SeatBookingManager:
    # Build the manager, optionally with an injected logger collaborator.
    def __init__(self, logger=None):
        # Use the injected logger, or a module-level one by default.
        self.logger = logger if logger is not None else logging.getLogger(__name__)
        # Rooms are plain data: room id -> list of seat counts, one per row.
        self.rooms = {}
        # Screenings are plain data: screening id -> room id.
        self.screenings = {}
        # Bookings are plain data: (screening id, row, seat) -> client id.
        self.bookings = {}

    # Register a room; seats_per_row has one entry per row (rows/seats are 1-based).
    def add_room(self, room_id, seats_per_row):
        # Wrap everything so each failure is logged then rethrown generically.
        try:
            # A room needs at least one row.
            if not seats_per_row:
                # Reject a room without rows.
                raise ValueError("room %s must have at least one row" % room_id)
            # Every row needs at least one seat.
            if any(count < 1 for count in seats_per_row):
                # Reject a row without seats.
                raise ValueError("room %s has a row without seats" % room_id)
            # Refuse to silently overwrite an existing room.
            if room_id in self.rooms:
                # Reject the duplicate room id.
                raise ValueError("room %s already exists" % room_id)
            # Store a copy so later caller mutations cannot alter the room.
            self.rooms[room_id] = list(seats_per_row)
            # Return the room id as the generic result.
            return room_id
        # Catch any failure raised above.
        except Exception as exc:
            # Log the exception at this layer.
            self.logger.error("add_room failed: %s", exc)
            # Rethrow as the generic exception, without the original cause.
            raise ProcessingException(str(exc)) from None

    # Schedule a screening in an existing room.
    def add_screening(self, screening_id, room_id):
        # Wrap everything so each failure is logged then rethrown generically.
        try:
            # The room must exist.
            if room_id not in self.rooms:
                # Reject an unknown room.
                raise ValueError("unknown room %s" % room_id)
            # Refuse to silently overwrite an existing screening.
            if screening_id in self.screenings:
                # Reject the duplicate screening id.
                raise ValueError("screening %s already exists" % screening_id)
            # Link the screening to its room.
            self.screenings[screening_id] = room_id
            # Return the screening id as the generic result.
            return screening_id
        # Catch any failure raised above.
        except Exception as exc:
            # Log the exception at this layer.
            self.logger.error("add_screening failed: %s", exc)
            # Rethrow as the generic exception, without the original cause.
            raise ProcessingException(str(exc)) from None

    # Book one seat of a screening for a client; a taken seat is rejected.
    def book_seat(self, screening_id, row, seat, client_id):
        # Wrap everything so each failure is logged then rethrown generically.
        try:
            # The screening must exist.
            if screening_id not in self.screenings:
                # Reject an unknown screening.
                raise ValueError("unknown screening %s" % screening_id)
            # Look up the seat counts of the screening's room.
            seats_per_row = self.rooms[self.screenings[screening_id]]
            # The row must exist (1-based).
            if row < 1 or row > len(seats_per_row):
                # Reject an unknown row.
                raise ValueError("unknown row %s" % row)
            # The seat must exist in that row (1-based).
            if seat < 1 or seat > seats_per_row[row - 1]:
                # Reject an unknown seat.
                raise ValueError("unknown seat %s in row %s" % (seat, row))
            # Build the key identifying this seat for this screening.
            key = (screening_id, row, seat)
            # A seat that is already booked must be rejected.
            if key in self.bookings:
                # Reject the double booking.
                raise ValueError("seat %s of row %s already booked for screening %s" % (seat, row, screening_id))
            # Record who booked the seat.
            self.bookings[key] = client_id
            # Return the booked key as the generic result.
            return key
        # Catch any failure raised above.
        except Exception as exc:
            # Log the exception at this layer.
            self.logger.error("book_seat failed: %s", exc)
            # Rethrow as the generic exception, without the original cause.
            raise ProcessingException(str(exc)) from None

    # List the availability of every seat of a screening.
    def get_seat_availability(self, screening_id):
        # Wrap everything so each failure is logged then rethrown generically.
        try:
            # The screening must exist.
            if screening_id not in self.screenings:
                # Reject an unknown screening.
                raise ValueError("unknown screening %s" % screening_id)
            # Look up the seat counts of the screening's room.
            seats_per_row = self.rooms[self.screenings[screening_id]]
            # Accumulate one entry per seat.
            result = []
            # Walk the rows in order (1-based).
            for row, count in enumerate(seats_per_row, start=1):
                # Walk the seats of the row in order (1-based).
                for seat in range(1, count + 1):
                    # A seat is available when no booking exists for it.
                    result.append({
                        "row": row,
                        "seat": seat,
                        "available": (screening_id, row, seat) not in self.bookings,
                    })
            # Return every seat with its availability.
            return result
        # Catch any failure raised above.
        except Exception as exc:
            # Log the exception at this layer.
            self.logger.error("get_seat_availability failed: %s", exc)
            # Rethrow as the generic exception, without the original cause.
            raise ProcessingException(str(exc)) from None
