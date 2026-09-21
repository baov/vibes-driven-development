"""Seat booking service for screening reservations."""

# Represents a physical room layout.
class Room:
    def __init__(self, room_id, rows, seats_per_row):
        # Unique identifier for the room.
        self.room_id = room_id
        # Number of rows in the room.
        self.rows = rows
        # Number of seats per row.
        self.seats_per_row = seats_per_row


# Represents a screening event in a room.
class Screening:
    def __init__(self, screening_id, room):
        # Unique identifier for the screening.
        self.screening_id = screening_id
        # The room where the screening takes place.
        self.room = room


# Raised when a booking violates constraints.
class BookingException(Exception):
    pass


# Raised when processing encounters an unexpected error at the service layer.
class ProcessingException(Exception):
    pass


# Manages seat bookings for screenings.
class SeatBookingManager:
    def __init__(self):
        # Map from screening_id to dict of {(row, seat): booked_client_name}.
        self._bookings = {}

    def book_seat(self, screening, row, seat, client_name):
        """
        Book a seat for a client at a screening.

        Raises BookingException if the seat is already booked or invalid.
        """
        try:
            # Validate row and seat numbers.
            if row < 0 or row >= screening.room.rows:
                raise BookingException(f"Invalid row: {row}")
            if seat < 0 or seat >= screening.room.seats_per_row:
                raise BookingException(f"Invalid seat: {seat}")

            # Initialize screening bookings if not present.
            if screening.screening_id not in self._bookings:
                self._bookings[screening.screening_id] = {}

            # Check if seat is already booked.
            seat_key = (row, seat)
            if seat_key in self._bookings[screening.screening_id]:
                raise BookingException(f"Seat ({row}, {seat}) is already booked")

            # Book the seat for the client.
            self._bookings[screening.screening_id][seat_key] = client_name
        except BookingException:
            # Re-raise domain constraint violations.
            raise
        except Exception as e:
            # Wrap unexpected exceptions.
            raise ProcessingException(str(e))

    def get_availability(self, screening):
        """
        Get availability status for all seats in a screening.

        Returns a dict: {(row, seat): booked_client_name_or_None}
        None means the seat is available.
        """
        try:
            # Initialize result with all seats marked as available.
            availability = {}
            for row in range(screening.room.rows):
                for seat in range(screening.room.seats_per_row):
                    seat_key = (row, seat)
                    availability[seat_key] = None

            # Fill in booked seats.
            if screening.screening_id in self._bookings:
                for seat_key, client_name in self._bookings[screening.screening_id].items():
                    availability[seat_key] = client_name

            return availability
        except Exception as e:
            # Log and wrap unexpected exceptions.
            raise ProcessingException(str(e))
