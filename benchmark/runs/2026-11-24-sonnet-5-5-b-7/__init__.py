# Standard logging, used to log every exception at every layer
import logging
# Dataclasses give plain data entities (fields only)
from dataclasses import dataclass

# Module logger
logger = logging.getLogger(__name__)

# Booking status: seat is held
STATUS_ACTIVE = "ACTIVE"
# Booking status: booking was cancelled
STATUS_CANCELLED = "CANCELLED"
# Refund status: no refund happened (yet)
REFUND_NONE = "NONE"
# Refund status: refund went through
REFUND_REFUNDED = "REFUNDED"
# Refund status: refund failed, booking stays active
REFUND_FAILED = "REFUND_FAILED"
# Hours before the start up to which a cancellation is accepted
CANCELLATION_DEADLINE_HOURS = 2
# Number of retries after the first refund attempt on a transient failure
REFUND_MAX_RETRIES = 3


# Generic exception exposed at the service boundary (lower-level causes are not leaked)
class ProcessingException(Exception):
    # Keep a short machine readable reason next to the message
    def __init__(self, reason):
        # Initialise the base exception with the reason as message
        super().__init__(reason)
        # Store the reason for callers
        self.reason = reason


# Raised by a payment gateway on a temporary failure (the refund may be retried)
class TransientGatewayError(Exception):
    # Marker class, no behavior
    pass


# Raised by a payment gateway on a definitive failure (retrying is useless)
class PermanentGatewayError(Exception):
    # Marker class, no behavior
    pass


# Raised by a payment gateway that cannot be reached at all
class GatewayUnavailableError(Exception):
    # Marker class, no behavior
    pass


# Room entity: plain data, a grid of rows x seats
@dataclass
class Room:
    # Room name
    name: str
    # Number of rows (rows are numbered from 1)
    rows: int
    # Number of seats per row (seats are numbered from 1)
    seats_per_row: int


# Screening entity: plain data
@dataclass
class Screening:
    # Screening identifier
    id: str
    # Start time (datetime, same timezone convention as the service clock)
    start_time: object
    # Room where the screening takes place
    room: Room
    # Price in cents (integer primitive, avoids float rounding on money)
    price: int


# Booking entity: plain data
@dataclass
class Booking:
    # Booking identifier
    id: str
    # Screening identifier
    screening_id: str
    # Client identifier
    client_id: str
    # Seat row
    row: int
    # Seat number in the row
    seat: int
    # Amount paid, in cents
    amount: int
    # ACTIVE or CANCELLED
    status: str = STATUS_ACTIVE
    # NONE, REFUNDED or REFUND_FAILED
    refund_status: str = REFUND_NONE


# Local date helper (kept in this module on purpose, no shared import)
class DateUtil:
    # True when `now` is at least `hours` hours before `start_time`
    def is_at_least_hours_before(self, now, start_time, hours):
        # Seconds between now and the start
        seconds_left = (start_time - now).total_seconds()
        # Cancellation is still allowed exactly at the deadline (inclusive)
        return seconds_left >= hours * 3600


# Service holding the booking and cancellation business rules
class BookingManagerService:
    # gateway: object exposing refund(booking_id, amount); clock: callable returning the current datetime
    def __init__(self, gateway, clock, date_util=None):
        # Payment gateway passed by the caller
        self.gateway = gateway
        # Clock passed by the caller (makes time controllable)
        self.clock = clock
        # Date helper, default to the local one
        self.date_util = date_util if date_util is not None else DateUtil()
        # Screenings by id
        self.screenings = {}
        # Bookings by id
        self.bookings = {}
        # Counter used to build booking ids
        self.sequence = 0

    # Register a screening so seats can be booked for it
    def add_screening(self, screening):
        # Store the screening under its id
        self.screenings[screening.id] = screening
        # Return it for convenience
        return screening

    # Book a seat; rejects unknown screening, out of room seats and already booked seats
    def book_seat(self, screening_id, client_id, row, seat):
        # Look the screening up
        info = self.screenings.get(screening_id)
        # Unknown screening: log then reject
        if info is None:
            # Log the failure at this layer
            logger.error("book_seat: unknown screening %s", screening_id)
            # Reject with a generic exception
            raise ProcessingException("unknown_screening")
        # Seat outside the room grid: log then reject
        if not (1 <= row <= info.room.rows and 1 <= seat <= info.room.seats_per_row):
            # Log the failure at this layer
            logger.error("book_seat: invalid seat %s/%s", row, seat)
            # Reject with a generic exception
            raise ProcessingException("invalid_seat")
        # Check every existing booking for the same seat
        for existing in self.bookings.values():
            # An active booking on the same screening, row and seat blocks the new one
            if (existing.status == STATUS_ACTIVE and existing.screening_id == screening_id
                    and existing.row == row and existing.seat == seat):
                # Log the failure at this layer
                logger.error("book_seat: seat already booked %s/%s", row, seat)
                # Reject with a generic exception
                raise ProcessingException("seat_already_booked")
        # Next sequence number
        self.sequence += 1
        # Build the new booking, paying the screening price
        result = Booking(id="B%d" % self.sequence, screening_id=screening_id, client_id=client_id,
                         row=row, seat=seat, amount=info.price)
        # Store it
        self.bookings[result.id] = result
        # Hand it back
        return result

    # Cancel a booking (up to 2h before the start) and refund it through the gateway
    def cancel_booking(self, booking_id):
        # Look the booking up
        info = self.bookings.get(booking_id)
        # Unknown booking: log then reject
        if info is None:
            # Log the failure at this layer
            logger.error("cancel_booking: unknown booking %s", booking_id)
            # Reject with a generic exception
            raise ProcessingException("unknown_booking")
        # Already cancelled booking: log then reject
        if info.status == STATUS_CANCELLED:
            # Log the failure at this layer
            logger.error("cancel_booking: already cancelled %s", booking_id)
            # Reject with a generic exception
            raise ProcessingException("already_cancelled")
        # Screening of the booking
        screening = self.screenings[info.screening_id]
        # Too late to cancel: log then reject
        if not self.date_util.is_at_least_hours_before(self.clock(), screening.start_time,
                                                       CANCELLATION_DEADLINE_HOURS):
            # Log the failure at this layer
            logger.error("cancel_booking: too late %s", booking_id)
            # Reject with a generic exception
            raise ProcessingException("too_late")
        # First attempt plus the allowed retries
        for attempt in range(REFUND_MAX_RETRIES + 1):
            # Try the refund
            try:
                # Ask the gateway to refund the amount paid
                self.gateway.refund(info.id, info.amount)
            # Temporary failure: retry unless attempts are exhausted
            except TransientGatewayError:
                # Log the exception at this layer
                logger.exception("cancel_booking: transient refund failure %s (attempt %d)", booking_id, attempt + 1)
                # Retries exhausted: booking stays active, refund marked failed
                if attempt == REFUND_MAX_RETRIES:
                    # Record the failed refund
                    info.refund_status = REFUND_FAILED
                    # Return the still active booking
                    return info
                # Otherwise go to the next attempt
                continue
            # Definitive failure: booking stays active
            except PermanentGatewayError:
                # Log the exception at this layer
                logger.exception("cancel_booking: permanent refund failure %s", booking_id)
                # Record the failed refund
                info.refund_status = REFUND_FAILED
                # Return the still active booking
                return info
            # Gateway down: cancellation is rejected, booking untouched
            except GatewayUnavailableError:
                # Log the exception at this layer
                logger.exception("cancel_booking: gateway unavailable %s", booking_id)
                # Reject with a generic exception (cause omitted)
                raise ProcessingException("gateway_unavailable")
            # Refund went through: leave the retry loop
            break
        # Booking is now cancelled
        info.status = STATUS_CANCELLED
        # And refunded
        info.refund_status = REFUND_REFUNDED
        # Hand it back
        return info

    # Refund status of a booking: NONE, REFUNDED or REFUND_FAILED
    def get_refund_status(self, booking_id):
        # Look the booking up
        info = self.bookings.get(booking_id)
        # Unknown booking: log then reject
        if info is None:
            # Log the failure at this layer
            logger.error("get_refund_status: unknown booking %s", booking_id)
            # Reject with a generic exception
            raise ProcessingException("unknown_booking")
        # Expose the refund status
        return info.refund_status
