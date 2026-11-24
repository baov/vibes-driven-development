# Standard library logging, used to record every rejected booking request.
import logging
# Dataclass decorator and field helper, used to declare the plain data holder for a screening.
from dataclasses import dataclass, field

# Module logger; each layer that sees a failure logs it here before rethrowing.
logger = logging.getLogger(__name__)


# Generic failure raised at the booking boundary so callers never see lower-level details.
class ProcessingException(Exception):
    # Carries the message only; no extra behavior is needed.
    pass


# Plain data holder for a screening and the room layout it takes place in.
@dataclass
class Screening:
    # Identifier of the screening.
    screening_id: str
    # Number of rows in the room, numbered 1 to rows.
    rows: int
    # Number of seats in each row, numbered 1 to seats_per_row.
    seats_per_row: int
    # Booked seats keyed by (row, seat), each mapped to the id of the client who booked it.
    bookings: dict = field(default_factory=dict)


# Service that registers screenings and manages seat bookings for them.
class SeatBookingManager:
    # Creates a manager with no screenings registered yet.
    def __init__(self):
        # Registered screenings keyed by screening id.
        self._screenings = {}

    # Registers a screening together with the rows and seats of its room.
    def add_screening(self, screening_id, rows, seats_per_row):
        # Store a new screening object under its id.
        self._screenings[screening_id] = Screening(screening_id, rows, seats_per_row)

    # Books one seat for a client; rejects unknown screenings, nonexistent seats and seats already booked.
    def book_seat(self, screening_id, row, seat, client_id):
        # Start the guarded section that turns domain failures into ProcessingException.
        try:
            # Reject the request when the screening was never registered.
            if screening_id not in self._screenings:
                # Raise a lower-level error that the boundary below wraps.
                raise ValueError(f"unknown screening {screening_id}")
            # Look up the screening the seat belongs to.
            screening = self._screenings[screening_id]
            # Reject the request when the row or seat is outside the room layout.
            if not (1 <= row <= screening.rows and 1 <= seat <= screening.seats_per_row):
                # Raise a lower-level error that the boundary below wraps.
                raise ValueError(f"seat {row}-{seat} does not exist in screening {screening_id}")
            # Reject the request when the seat is already booked.
            if (row, seat) in screening.bookings:
                # Raise a lower-level error that the boundary below wraps.
                raise ValueError(f"seat {row}-{seat} is already booked in screening {screening_id}")
            # Record the booking against the requesting client.
            screening.bookings[(row, seat)] = client_id
        # Handle the domain failures raised above.
        except ValueError as exc:
            # Log the rejected request before passing it on.
            logger.error("Seat booking rejected: %s", exc)
            # Wrap the failure in the generic exception of this layer.
            raise ProcessingException(str(exc))

    # Returns the availability of every seat of a screening, keyed by (row, seat); True means available.
    def get_seat_availability(self, screening_id):
        # Start the guarded section that turns domain failures into ProcessingException.
        try:
            # Reject the request when the screening was never registered.
            if screening_id not in self._screenings:
                # Raise a lower-level error that the boundary below wraps.
                raise ValueError(f"unknown screening {screening_id}")
            # Look up the screening whose seats are reported.
            screening = self._screenings[screening_id]
            # Start the result mapping that will hold one entry per seat.
            availability = {}
            # Visit every row of the room.
            for row in range(1, screening.rows + 1):
                # Visit every seat of the current row.
                for seat in range(1, screening.seats_per_row + 1):
                    # Mark the seat as available when no booking exists for it.
                    availability[(row, seat)] = (row, seat) not in screening.bookings
            # Return the complete availability mapping.
            return availability
        # Handle the domain failures raised above.
        except ValueError as exc:
            # Log the rejected request before passing it on.
            logger.error("Seat availability request rejected: %s", exc)
            # Wrap the failure in the generic exception of this layer.
            raise ProcessingException(str(exc))
