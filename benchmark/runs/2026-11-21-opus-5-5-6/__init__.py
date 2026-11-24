"""Seat booking for cinema screenings."""

# Import dataclass to declare plain data entities.
from dataclasses import dataclass, field
# Import logging so every rejected operation is observable.
import logging
# Import threading so concurrent bookings of the same seat cannot both succeed.
import threading

# Create the module logger.
logger = logging.getLogger(__name__)


# Declare the generic exception raised at the service boundary.
class ProcessingException(Exception):
    # Mark the class body as intentionally empty.
    pass


# Declare the error raised when a screening id is not registered.
class UnknownScreeningError(ProcessingException):
    # Mark the class body as intentionally empty.
    pass


# Declare the error raised when a row/seat does not exist in the room.
class UnknownSeatError(ProcessingException):
    # Mark the class body as intentionally empty.
    pass


# Declare the error raised when a seat is already booked for the screening.
class SeatAlreadyBookedError(ProcessingException):
    # Mark the class body as intentionally empty.
    pass


# Declare a room: a name and the number of seats in each row, keyed by row label.
@dataclass
class Room:
    # Store the room name.
    name: str
    # Store the seat count of each row, e.g. {"A": 10, "B": 12}.
    rows: dict


# Declare a screening taking place in a room.
@dataclass
class Screening:
    # Store the screening identifier.
    screening_id: str
    # Store the room where the screening takes place.
    room: Room


# Declare a booking of one seat by one client for one screening.
@dataclass
class Booking:
    # Store the screening identifier.
    screening_id: str
    # Store the client identifier.
    client_id: str
    # Store the row label.
    row: str
    # Store the seat number within the row (1-based).
    seat: int


# Declare the availability of one seat for a screening.
@dataclass
class SeatAvailability:
    # Store the row label.
    row: str
    # Store the seat number within the row (1-based).
    seat: int
    # Store whether the seat can still be booked.
    available: bool


# Declare the service that registers screenings, books seats and reports availability.
@dataclass
class SeatBookingManager:
    # Store screenings by identifier.
    screenings: dict = field(default_factory=dict)
    # Store bookings by (screening_id, row, seat).
    bookings: dict = field(default_factory=dict)
    # Guard the check-then-book sequence against concurrent callers.
    lock: threading.Lock = field(default_factory=threading.Lock)

    # Register a screening so seats can be booked for it.
    def add_screening(self, screening):
        # Index the screening by its identifier.
        self.screenings[screening.screening_id] = screening

    # Book a seat for a client; reject unknown screenings, unknown seats and already booked seats.
    def book_seat(self, screening_id, client_id, row, seat):
        # Look up the screening.
        data = self.screenings.get(screening_id)
        # Reject a screening that was never registered.
        if data is None:
            # Log the rejection before raising it.
            logger.warning("Unknown screening %s", screening_id)
            # Raise the rejection.
            raise UnknownScreeningError(f"Unknown screening {screening_id}")
        # Reject a row that does not exist or a seat number outside the row.
        if row not in data.room.rows or not 1 <= seat <= data.room.rows[row]:
            # Log the rejection before raising it.
            logger.warning("Unknown seat %s%s for screening %s", row, seat, screening_id)
            # Raise the rejection.
            raise UnknownSeatError(f"Unknown seat {row}{seat} for screening {screening_id}")
        # Build the key identifying this seat for this screening.
        key = (screening_id, row, seat)
        # Make the availability check and the booking a single atomic step.
        with self.lock:
            # Reject a seat that is already booked.
            if key in self.bookings:
                # Log the rejection before raising it.
                logger.warning("Seat %s%s already booked for screening %s", row, seat, screening_id)
                # Raise the rejection.
                raise SeatAlreadyBookedError(f"Seat {row}{seat} already booked for screening {screening_id}")
            # Create the booking.
            result = Booking(screening_id, client_id, row, seat)
            # Record the booking.
            self.bookings[key] = result
        # Return the booking to the caller.
        return result

    # Return the availability of every seat of a screening, row by row, seat by seat.
    def get_seat_availability(self, screening_id):
        # Look up the screening.
        data = self.screenings.get(screening_id)
        # Reject a screening that was never registered.
        if data is None:
            # Log the rejection before raising it.
            logger.warning("Unknown screening %s", screening_id)
            # Raise the rejection.
            raise UnknownScreeningError(f"Unknown screening {screening_id}")
        # Read bookings under the lock so the snapshot is consistent.
        with self.lock:
            # Build one entry per seat, available when no booking exists for it.
            result = [
                SeatAvailability(row, seat, (screening_id, row, seat) not in self.bookings)
                for row, seat_count in data.room.rows.items()
                for seat in range(1, seat_count + 1)
            ]
        # Return the availability list.
        return result
