# logging is used to record every exception at every layer
import logging
# dataclass gives us plain data entities
from dataclasses import dataclass
# timedelta is used for the cancellation window
from datetime import datetime, timedelta

# module-level logger
logger = logging.getLogger(__name__)

# number of retries after the first refund attempt (transient failures only)
MAX_REFUND_RETRIES = 3
# cancellation is allowed up to this long before the screening starts
CANCELLATION_WINDOW = timedelta(hours=2)


# generic exception exposed at the service boundary; carries a reason code only
class ProcessingException(Exception):
    # constructor takes the reason code
    def __init__(self, reason):
        # initialise the base exception with the reason as message
        super().__init__(reason)
        # keep the reason so callers can tell rejections apart
        self.reason = reason


# raised by a payment gateway on a temporary failure (retry is worthwhile)
class TransientGatewayException(Exception):
    # no extra behavior
    pass


# raised by a payment gateway on a definitive failure (retry is useless)
class PermanentGatewayException(Exception):
    # no extra behavior
    pass


# raised by a payment gateway that cannot be reached at all
class GatewayUnavailableException(Exception):
    # no extra behavior
    pass


# plain data: a room with rows and seats per row
@dataclass
class Room:
    # number of rows
    rows: int
    # number of seats in each row
    seats_per_row: int


# plain data: a screening with a start time, a room and a price
@dataclass
class Screening:
    # screening identifier
    id: int
    # start time of the screening
    start: datetime
    # room where the screening takes place
    room: Room
    # price of one seat
    price: float


# plain data: a seat booking and its refund status
@dataclass
class Booking:
    # booking identifier
    id: int
    # client who booked
    client: str
    # booked screening
    screening_id: int
    # booked row (1-based)
    row: int
    # booked seat in the row (1-based)
    seat: int
    # ACTIVE or CANCELLED
    status: str = "ACTIVE"
    # NONE, REFUNDED or FAILED
    refund_status: str = "NONE"


# service holding the booking business rules; the gateway is passed in
class BookingManagerService:
    # gateway must expose refund(booking_id, amount); clock returns the current datetime
    def __init__(self, gateway, clock=datetime.now):
        # payment gateway used for refunds
        self.gateway = gateway
        # clock used for the cancellation window
        self.clock = clock
        # screenings by id
        self.screenings = {}
        # bookings by id
        self.bookings = {}
        # next booking identifier
        self.next_id = 1

    # register a screening so that seats can be booked on it
    def add_screening(self, screening):
        # store the screening under its id
        self.screenings[screening.id] = screening

    # book one seat of a screening for a client
    def book_seat(self, client, screening_id, row, seat):
        # look the screening up
        info = self.screenings.get(screening_id)
        # unknown screening is rejected
        if info is None:
            # log the rejection
            logger.error("book_seat rejected: unknown screening %s", screening_id)
            # reject with a reason code
            raise ProcessingException("UNKNOWN_SCREENING")
        # a seat outside the room is rejected
        if not (1 <= row <= info.room.rows and 1 <= seat <= info.room.seats_per_row):
            # log the rejection
            logger.error("book_seat rejected: invalid seat %s/%s", row, seat)
            # reject with a reason code
            raise ProcessingException("INVALID_SEAT")
        # look for an active booking on the same seat
        for data in self.bookings.values():
            # same screening, same seat, still active
            if (data.status == "ACTIVE" and data.screening_id == screening_id
                    and data.row == row and data.seat == seat):
                # log the rejection
                logger.error("book_seat rejected: seat %s/%s already booked", row, seat)
                # reject with a reason code
                raise ProcessingException("SEAT_ALREADY_BOOKED")
        # create the booking
        result = Booking(self.next_id, client, screening_id, row, seat)
        # store it
        self.bookings[result.id] = result
        # prepare the next identifier
        self.next_id += 1
        # hand the booking back
        return result

    # cancel a booking (up to two hours before the start) and refund it
    def cancel_booking(self, booking_id):
        # look the booking up
        result = self.bookings.get(booking_id)
        # unknown booking is rejected
        if result is None:
            # log the rejection
            logger.error("cancel_booking rejected: unknown booking %s", booking_id)
            # reject with a reason code
            raise ProcessingException("UNKNOWN_BOOKING")
        # an already cancelled booking is rejected
        if result.status == "CANCELLED":
            # log the rejection
            logger.error("cancel_booking rejected: booking %s already cancelled", booking_id)
            # reject with a reason code
            raise ProcessingException("ALREADY_CANCELLED")
        # screening of the booking
        info = self.screenings[result.screening_id]
        # cancellation is only possible up to two hours before the start
        if self.clock() > info.start - CANCELLATION_WINDOW:
            # log the rejection
            logger.error("cancel_booking rejected: booking %s too late", booking_id)
            # reject with a reason code
            raise ProcessingException("TOO_LATE")
        # first attempt plus the retries
        for attempt in range(1 + MAX_REFUND_RETRIES):
            # try to refund through the gateway
            try:
                # ask the gateway to refund the price
                self.gateway.refund(result.id, info.price)
                # refund went through: the booking is cancelled
                result.status = "CANCELLED"
                # record the refund
                result.refund_status = "REFUNDED"
                # done
                return result
            # temporary failure: log it and try again
            except TransientGatewayException:
                # log with stack trace, then loop
                logger.exception("refund attempt %s failed transiently for booking %s", attempt + 1, booking_id)
            # definitive failure: the booking stays active
            except PermanentGatewayException:
                # log with stack trace
                logger.exception("refund failed permanently for booking %s", booking_id)
                # record the failure
                result.refund_status = "FAILED"
                # wrap in the generic exception, cause omitted
                raise ProcessingException("REFUND_FAILED") from None
            # gateway down: the cancellation is rejected
            except GatewayUnavailableException:
                # log with stack trace
                logger.exception("gateway unavailable for booking %s", booking_id)
                # wrap in the generic exception, cause omitted
                raise ProcessingException("GATEWAY_UNAVAILABLE") from None
        # all attempts failed transiently: the booking stays active
        logger.error("refund retries exhausted for booking %s", booking_id)
        # record the failure
        result.refund_status = "FAILED"
        # reject with a reason code
        raise ProcessingException("REFUND_FAILED")

    # expose the refund status of a booking
    def get_refund_status(self, booking_id):
        # look the booking up
        result = self.bookings.get(booking_id)
        # unknown booking is rejected
        if result is None:
            # log the rejection
            logger.error("get_refund_status rejected: unknown booking %s", booking_id)
            # reject with a reason code
            raise ProcessingException("UNKNOWN_BOOKING")
        # NONE, REFUNDED or FAILED
        return result.refund_status
