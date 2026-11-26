# datetime builds the fixed instants used by the mocked clock
from datetime import datetime
# Mock replaces every collaborator, value objects included
from unittest import TestCase, main
from unittest.mock import Mock

# class under test and the exceptions it handles
from seat_booking import (BookingManagerService, GatewayUnavailableException,
                          PermanentGatewayException, ProcessingException,
                          TransientGatewayException)


# one test file per class, one test per method (numbered when several paths must run)
class BookingManagerServiceTest(TestCase):
    # build the service with a mocked gateway, mocked clock and mocked screening
    def setUp(self):
        # mocked payment gateway
        self.gateway = Mock()
        # mocked clock: six hours before the screening
        self.clock = Mock(return_value=datetime(2026, 1, 1, 14))
        # mocked room
        room = Mock(rows=3, seats_per_row=4)
        # mocked screening starting at 20:00
        self.screening = Mock(id=1, start=datetime(2026, 1, 1, 20), room=room, price=12.5)
        # service under test
        self.service = BookingManagerService(self.gateway, self.clock)
        # register the mocked screening
        self.service.add_screening(self.screening)

    # add_screening stores the screening
    def test_add_screening(self):
        # the screening is known by its id
        self.assertIn(1, self.service.screenings)

    # book_seat nominal path
    def test_book_seat(self):
        # booking is active
        self.assertEqual(self.service.book_seat("ann", 1, 1, 1).status, "ACTIVE")

    # book_seat with an unknown screening
    def test_book_seat2(self):
        # rejected
        with self.assertRaises(ProcessingException):
            # unknown screening id
            self.service.book_seat("ann", 99, 1, 1)

    # book_seat with a seat outside the room
    def test_book_seat3(self):
        # rejected
        with self.assertRaises(ProcessingException):
            # row 4 does not exist
            self.service.book_seat("ann", 1, 4, 1)

    # book_seat on an already booked seat
    def test_book_seat4(self):
        # first booking
        self.service.book_seat("ann", 1, 1, 1)
        # rejected
        with self.assertRaises(ProcessingException):
            # same seat
            self.service.book_seat("bob", 1, 1, 1)

    # cancel_booking nominal path: the gateway is asked to refund the price
    def test_cancel_booking(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # cancel
        self.service.cancel_booking(booking.id)
        # interaction with the gateway
        self.gateway.refund.assert_called_once_with(booking.id, 12.5)

    # cancel_booking with an unknown booking
    def test_cancel_booking2(self):
        # rejected
        with self.assertRaises(ProcessingException):
            # unknown id
            self.service.cancel_booking(99)

    # cancel_booking on an already cancelled booking
    def test_cancel_booking3(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # first cancellation
        self.service.cancel_booking(booking.id)
        # rejected
        with self.assertRaises(ProcessingException):
            # second cancellation
            self.service.cancel_booking(booking.id)

    # cancel_booking less than two hours before the start
    def test_cancel_booking4(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # one hour before the start
        self.clock.return_value = datetime(2026, 1, 1, 19)
        # rejected
        with self.assertRaises(ProcessingException):
            # too late
            self.service.cancel_booking(booking.id)

    # cancel_booking retries a transient failure
    def test_cancel_booking5(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # two transient failures then success
        self.gateway.refund.side_effect = [TransientGatewayException(), TransientGatewayException(), None]
        # cancel
        self.service.cancel_booking(booking.id)
        # three calls
        self.assertEqual(self.gateway.refund.call_count, 3)

    # cancel_booking gives up after three retries
    def test_cancel_booking6(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # always transient
        self.gateway.refund.side_effect = TransientGatewayException()
        # rejected
        with self.assertRaises(ProcessingException):
            # cancel
            self.service.cancel_booking(booking.id)

    # cancel_booking on a permanent failure
    def test_cancel_booking7(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # permanent failure
        self.gateway.refund.side_effect = PermanentGatewayException()
        # rejected
        with self.assertRaises(ProcessingException):
            # cancel
            self.service.cancel_booking(booking.id)

    # cancel_booking when the gateway is unavailable
    def test_cancel_booking8(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # gateway down
        self.gateway.refund.side_effect = GatewayUnavailableException()
        # rejected
        with self.assertRaises(ProcessingException):
            # cancel
            self.service.cancel_booking(booking.id)

    # get_refund_status of a known booking
    def test_get_refund_status(self):
        # book
        booking = self.service.book_seat("ann", 1, 1, 1)
        # nothing refunded yet
        self.assertEqual(self.service.get_refund_status(booking.id), "NONE")

    # get_refund_status of an unknown booking
    def test_get_refund_status2(self):
        # rejected
        with self.assertRaises(ProcessingException):
            # unknown id
            self.service.get_refund_status(99)


# allow running the file directly
if __name__ == "__main__":
    # run the tests
    main()
