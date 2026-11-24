"""Seat booking for cinema screenings."""

# threading gives us a lock so two concurrent bookings cannot both win the same seat
import threading


# Base error for every booking failure, so callers can catch a single type
class BookingError(Exception):
    pass


# Raised when the requested screening has never been registered
class UnknownScreeningError(BookingError):
    pass


# Raised when the requested row/seat does not exist in the screening's room
class UnknownSeatError(BookingError):
    pass


# Raised when the requested seat is already taken for that screening
class SeatAlreadyBookedError(BookingError):
    pass


# A room is a named layout of rows, each row holding a fixed number of seats
class Room:
    # rows maps a row label (e.g. "A") to its seat count; seats are numbered from 1
    def __init__(self, name, rows):
        # Reject a room without rows, it could never host a booking
        if not rows:
            # Fail fast with an explicit message
            raise ValueError("a room needs at least one row")
        # Every row must contain at least one seat
        for row_label, seat_count in rows.items():
            # A row with zero or negative seats is a configuration mistake
            if seat_count < 1:
                # Name the faulty row so the mistake is easy to locate
                raise ValueError(f"row {row_label!r} must have at least one seat")
        # Keep the room name for display purposes
        self.name = name
        # Copy the layout so later changes to the caller's dict do not affect the room
        self.rows = dict(rows)

    # Tell whether (row, seat) designates a real seat of this room
    def has_seat(self, row, seat):
        # The row must exist and the seat number must be within 1..seat_count
        return row in self.rows and 1 <= seat <= self.rows[row]


# A screening is one showing taking place in one room
class Screening:
    # screening_id is a plain identifier, room is the Room it takes place in
    def __init__(self, screening_id, room):
        # Identifier used by clients to refer to this screening
        self.screening_id = screening_id
        # Room giving the seat layout of the screening
        self.room = room


# Entry point of the service: registers screenings, books seats, reports availability
class SeatBookingManager:
    def __init__(self):
        # Registered screenings, by screening id
        self._screenings = {}
        # Bookings per screening: {screening_id: {(row, seat): client_id}}
        self._bookings = {}
        # Serializes check-then-book so a seat can never be booked twice
        self._lock = threading.Lock()

    # Make a screening known to the service so its seats can be booked
    def add_screening(self, screening):
        # Hold the lock so registration does not race with bookings
        with self._lock:
            # Registering the same id twice would silently wipe existing bookings
            if screening.screening_id in self._screenings:
                # Refuse instead of overwriting
                raise ValueError(f"screening {screening.screening_id!r} already exists")
            # Store the screening
            self._screenings[screening.screening_id] = screening
            # Start with no booked seats
            self._bookings[screening.screening_id] = {}

    # Book (row, seat) of a screening for a client; rejects an already booked seat
    def book_seat(self, screening_id, row, seat, client_id):
        # Hold the lock for the whole check-then-write sequence
        with self._lock:
            # Resolve the screening, failing on unknown ids
            screening = self._get_screening(screening_id)
            # The seat must exist in the screening's room
            if not screening.room.has_seat(row, seat):
                # Report the invalid seat
                raise UnknownSeatError(f"seat {row}{seat} does not exist in room {screening.room.name!r}")
            # Bookings already made for this screening
            booked = self._bookings[screening_id]
            # A seat can only be booked once per screening
            if (row, seat) in booked:
                # Reject the double booking
                raise SeatAlreadyBookedError(f"seat {row}{seat} is already booked for screening {screening_id!r}")
            # Record the booking against the client
            booked[(row, seat)] = client_id

    # List every seat of a screening with whether it is still available
    def get_seat_availability(self, screening_id):
        # Hold the lock so the snapshot is consistent
        with self._lock:
            # Resolve the screening, failing on unknown ids
            screening = self._get_screening(screening_id)
            # Bookings already made for this screening
            booked = self._bookings[screening_id]
            # One entry per seat, in room order (rows as declared, seats ascending)
            return [
                {"row": row, "seat": seat, "available": (row, seat) not in booked}
                for row, seat_count in screening.room.rows.items()
                for seat in range(1, seat_count + 1)
            ]

    # Look up a screening or raise UnknownScreeningError
    def _get_screening(self, screening_id):
        # Fetch without raising KeyError
        screening = self._screenings.get(screening_id)
        # An unknown id is a caller error worth naming explicitly
        if screening is None:
            # Report which id was not found
            raise UnknownScreeningError(f"screening {screening_id!r} does not exist")
        # Found
        return screening
