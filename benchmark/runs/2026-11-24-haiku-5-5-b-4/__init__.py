# Import logging so that every layer can record the exceptions it passes through
import logging
# Import uuid to generate unique booking identifiers
import uuid
# Import dataclass to declare plain data holders without boilerplate
from dataclasses import dataclass
# Import datetime and timedelta to express the cancellation cut-off window
from datetime import datetime, timedelta

# Create the logger shared by every class in this module
LOGGER = logging.getLogger(__name__)
# Set the minimum lead time before a screening starts for a cancellation to be accepted
CANCELLATION_WINDOW = timedelta(hours=2)
# Set how many times a transient gateway failure is retried after the first attempt
MAX_REFUND_RETRIES = 3


# Plain data describing the seating layout of a room
@dataclass
class RoomData:
    # Number of rows in the room
    rows: int
    # Number of seats in each row
    seats_per_row: int


# Plain data describing one screening of a film
@dataclass
class ScreeningData:
    # Identifier of the screening
    screening_id: str
    # Moment the screening starts
    start_time: datetime
    # Room in which the screening takes place
    room: RoomData
    # Price of one seat for this screening
    price: float


# Plain data describing one seat booked by a client
@dataclass
class BookingData:
    # Identifier of the booking
    booking_id: str
    # Screening the seat was booked for
    screening: ScreeningData
    # Row index of the booked seat
    row: int
    # Seat index within the row
    seat: int
    # Client who made the booking
    client_id: str
    # Either "active" or "cancelled"
    status: str
    # Either "none", "refunded" or "failed"
    refund_status: str


# Generic exception raised to clients so that implementation details do not leak
class ProcessingException(Exception):
    pass


# Exception raised by a payment gateway, carrying the kind of failure
class PaymentGatewayException(Exception):
    # Store the failure kind: "transient", "permanent" or "unavailable"
    def __init__(self, kind):
        # Forward the kind to the base exception so it appears in the message
        super().__init__(kind)
        # Keep the failure kind so the caller can choose how to react
        self.kind = kind


# Service that books seats, cancels bookings and reports refund outcomes
class BookingManager:
    # Store the payment gateway and initialise the booking registries
    def __init__(self, payment_gateway):
        # Keep the gateway used to refund cancelled bookings
        self._payment_gateway = payment_gateway
        # Index every booking by its identifier
        self._bookings = {}
        # Track the (screening, row, seat) keys that are currently held by an active booking
        self._active_seats = set()

    # Book one seat of a screening for a client, rejecting invalid or already booked seats
    def book_seat(self, screening, row, seat, client_id):
        # Reject a seat that lies outside the room layout
        if not (0 <= row < screening.room.rows and 0 <= seat < screening.room.seats_per_row):
            # Log the rejected booking before raising
            LOGGER.error("Seat %s/%s is outside the room of screening %s", row, seat, screening.screening_id)
            # Raise the generic exception to the client
            raise ProcessingException("Seat is outside the room layout")
        # Build the key identifying this seat for this screening
        seat_key = (screening.screening_id, row, seat)
        # Reject the booking when the seat is already held by an active booking
        if seat_key in self._active_seats:
            # Log the rejected booking before raising
            LOGGER.error("Seat %s/%s of screening %s is already booked", row, seat, screening.screening_id)
            # Raise the generic exception to the client
            raise ProcessingException("Seat is already booked")
        # Create the active booking for this seat
        booking = BookingData(
            # Generate a unique identifier for the booking
            booking_id=uuid.uuid4().hex,
            # Attach the screening the seat was booked for
            screening=screening,
            # Record the row of the booked seat
            row=row,
            # Record the seat index within the row
            seat=seat,
            # Record the client who made the booking
            client_id=client_id,
            # Mark the booking as active
            status="active",
            # No refund has been attempted yet
            refund_status="none",
        )
        # Register the booking by its identifier
        self._bookings[booking.booking_id] = booking
        # Hold the seat so that no other active booking can take it
        self._active_seats.add(seat_key)
        # Return the new booking to the client
        return booking

    # Cancel an active booking up to the cut-off window and refund it through the gateway
    def cancel_booking(self, booking_id, now):
        # Look up the booking by its identifier
        booking = self._bookings.get(booking_id)
        # Reject the cancellation when the booking is unknown
        if booking is None:
            # Log the rejected cancellation before raising
            LOGGER.error("Cannot cancel unknown booking %s", booking_id)
            # Raise the generic exception to the client
            raise ProcessingException("Unknown booking")
        # Reject the cancellation when the booking is no longer active
        if booking.status != "active":
            # Log the rejected cancellation before raising
            LOGGER.error("Booking %s is already cancelled", booking_id)
            # Raise the generic exception to the client
            raise ProcessingException("Booking is already cancelled")
        # Reject the cancellation when it comes later than the cut-off before the screening
        if now > booking.screening.start_time - CANCELLATION_WINDOW:
            # Log the rejected cancellation before raising
            LOGGER.error("Booking %s is inside the cancellation window", booking_id)
            # Raise the generic exception to the client
            raise ProcessingException("Cancellation window has passed")
        # Attempt the refund once plus up to the configured number of retries
        for attempt in range(MAX_REFUND_RETRIES + 1):
            # Send the refund of the seat price to the gateway
            try:
                # Call the gateway with the booking identifier and the seat price
                self._payment_gateway.refund(booking.booking_id, booking.screening.price)
            # Handle a failure reported by the gateway
            except PaymentGatewayException as error:
                # Log the gateway failure before deciding how to react
                LOGGER.warning("Refund attempt %s for booking %s failed: %s", attempt, booking_id, error.kind)
                # Retry a transient failure while attempts remain
                if error.kind == "transient" and attempt < MAX_REFUND_RETRIES:
                    # Move on to the next attempt
                    continue
                # Reject the cancellation when the gateway is unavailable, leaving the refund status untouched
                if error.kind == "unavailable":
                    # Log the rejected cancellation before raising
                    LOGGER.error("Payment gateway unavailable, cancelling booking %s rejected", booking_id)
                    # Raise the generic exception to the client
                    raise ProcessingException("Payment gateway unavailable, cancellation rejected")
                # Record the failed refund while the booking stays active
                booking.refund_status = "failed"
                # Log the rejected cancellation before raising
                LOGGER.error("Refund for booking %s failed, booking stays active", booking_id)
                # Raise the generic exception to the client
                raise ProcessingException("Refund failed, booking remains active")
            # Run only when the refund succeeded
            else:
                # Mark the booking as cancelled now that the refund went through
                booking.status = "cancelled"
                # Record that the refund was made
                booking.refund_status = "refunded"
                # Release the seat so that another client can book it
                self._active_seats.discard((booking.screening.screening_id, booking.row, booking.seat))
                # Stop here: the cancellation is complete
                return

    # Report the refund status of a booking
    def get_refund_status(self, booking_id):
        # Look up the booking by its identifier
        booking = self._bookings.get(booking_id)
        # Reject the query when the booking is unknown
        if booking is None:
            # Log the rejected query before raising
            LOGGER.error("Cannot read refund status of unknown booking %s", booking_id)
            # Raise the generic exception to the client
            raise ProcessingException("Unknown booking")
        # Return the refund status recorded on the booking
        return booking.refund_status
