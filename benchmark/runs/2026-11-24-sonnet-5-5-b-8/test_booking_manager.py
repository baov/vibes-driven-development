"""Mirror test of seat_booking.BookingManager: one test per method, collaborators mocked."""
# Import the datetime types used to drive the mocked clock.
from datetime import datetime, timedelta
# Import the unittest framework.
import unittest
# Import Mock to replace every collaborator.
from unittest.mock import Mock

# Import the classes under test and the gateway exceptions.
from seat_booking import (BookingManager, BookingRejectedException, ProcessingException,
                          TransientGatewayException, PermanentGatewayException,
                          GatewayUnavailableException)

# Start time shared by every test screening.
START = datetime(2030, 1, 1, 20, 0)


# Tests of BookingManager.
class BookingManagerTest(unittest.TestCase):

    # Build a manager with a mocked gateway, a mocked clock and a mocked screening.
    def setUp(self):
        # Mocked payment gateway.
        self.gateway = Mock()
        # Mocked clock, five hours before the screening.
        self.clock = Mock(return_value=START - timedelta(hours=5))
        # Mocked screening: 2 rows of 3 seats, price 1000 cents.
        self.screening = Mock(id="S1", start_time=START, rows=2, seats_per_row=3, price_cents=1000)
        # Manager under test.
        self.manager = BookingManager(self.gateway, self.clock)
        # Register the screening.
        self.manager.add_screening(self.screening)

    # Run an action expecting a rejection and return its reason.
    def reason_of(self, action, *args):
        # Expect a rejection.
        with self.assertRaises(BookingRejectedException) as ctx:
            # Run the action.
            action(*args)
        # Return the reason.
        return ctx.exception.reason

    # __init__ falls back to the system clock.
    def test___init__(self):
        # Build a manager without clock.
        info = BookingManager(self.gateway)
        # The default clock is datetime.now.
        self.assertEqual(info._clock, datetime.now)

    # add_screening registers the screening.
    def test_add_screening(self):
        # Register a second screening.
        other = Mock(id="S2")
        # The screening is returned.
        self.assertIs(self.manager.add_screening(other), other)

    # book_seat nominal case.
    def test_book_seat(self):
        # Book a seat.
        result = self.manager.book_seat("c1", "S1", 1, 1)
        # The booking is active and refund status is none.
        self.assertEqual((result.status, result.refund_status), ("active", "none"))

    # book_seat rejects a seat that is already booked.
    def test_book_seat2(self):
        # Book the seat once.
        self.manager.book_seat("c1", "S1", 1, 1)
        # Book it again.
        self.assertEqual(self.reason_of(self.manager.book_seat, "c2", "S1", 1, 1), "seat_already_booked")

    # book_seat rejects unknown screening, started screening and unknown seats.
    def test_book_seat3(self):
        # Unknown screening.
        self.assertEqual(self.reason_of(self.manager.book_seat, "c1", "nope", 1, 1), "unknown_screening")
        # Seat outside the room.
        self.assertEqual(self.reason_of(self.manager.book_seat, "c1", "S1", 3, 1), "unknown_seat")
        # Screening started.
        self.clock.return_value = START
        # Booking is rejected.
        self.assertEqual(self.reason_of(self.manager.book_seat, "c1", "S1", 1, 1), "screening_started")

    # book_seat wraps unexpected failures in ProcessingException.
    def test_book_seat4(self):
        # Make the clock explode.
        self.clock.side_effect = RuntimeError("boom")
        # The generic exception is raised.
        with self.assertRaises(ProcessingException):
            # Book a seat.
            self.manager.book_seat("c1", "S1", 1, 1)

    # book_seat accepts again a seat whose booking was cancelled.
    def test_book_seat5(self):
        # Book then cancel.
        self.manager.cancel_booking(self.manager.book_seat("c1", "S1", 1, 1).id)
        # The seat can be booked again.
        self.assertEqual(self.manager.book_seat("c2", "S1", 1, 1).status, "active")

    # cancel_booking nominal case: refund through the gateway.
    def test_cancel_booking(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Cancel it.
        self.manager.cancel_booking(info.id)
        # The gateway refunded the price once.
        self.gateway.refund.assert_called_once_with(info.id, 1000)
        # The booking is cancelled and refunded.
        self.assertEqual((info.status, self.manager.get_refund_status(info.id)), ("cancelled", "refunded"))

    # cancel_booking rejects unknown and already cancelled bookings.
    def test_cancel_booking2(self):
        # Unknown booking.
        self.assertEqual(self.reason_of(self.manager.cancel_booking, "nope"), "unknown_booking")
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # First cancellation works.
        self.manager.cancel_booking(info.id)
        # Second cancellation is rejected.
        self.assertEqual(self.reason_of(self.manager.cancel_booking, info.id), "already_cancelled")

    # cancel_booking is allowed exactly two hours before, rejected after.
    def test_cancel_booking3(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # One minute under two hours before the start.
        self.clock.return_value = START - timedelta(hours=2) + timedelta(minutes=1)
        # Rejected.
        self.assertEqual(self.reason_of(self.manager.cancel_booking, info.id), "too_late_to_cancel")
        # Exactly two hours before the start.
        self.clock.return_value = START - timedelta(hours=2)
        # Accepted.
        self.assertEqual(self.manager.cancel_booking(info.id).status, "cancelled")

    # cancel_booking retries transient failures up to three times.
    def test_cancel_booking4(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Three transient failures then success.
        self.gateway.refund.side_effect = [TransientGatewayException()] * 3 + [None]
        # Cancellation succeeds on the fourth call.
        self.assertEqual(self.manager.cancel_booking(info.id).status, "cancelled")
        # Four gateway calls.
        self.assertEqual(self.gateway.refund.call_count, 4)

    # cancel_booking gives up after the retries, booking stays active.
    def test_cancel_booking5(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Gateway always fails transiently.
        self.gateway.refund.side_effect = TransientGatewayException()
        # Cancellation rejected.
        self.assertEqual(self.reason_of(self.manager.cancel_booking, info.id), "refund_failed")
        # One attempt plus three retries, booking active, refund failed.
        self.assertEqual((self.gateway.refund.call_count, info.status, info.refund_status), (4, "active", "failed"))

    # cancel_booking: permanent failure, no retry, booking stays active.
    def test_cancel_booking6(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Gateway fails permanently.
        self.gateway.refund.side_effect = PermanentGatewayException()
        # Cancellation rejected.
        self.assertEqual(self.reason_of(self.manager.cancel_booking, info.id), "refund_failed")
        # Single attempt, booking active, refund failed.
        self.assertEqual((self.gateway.refund.call_count, info.status, info.refund_status), (1, "active", "failed"))

    # cancel_booking: gateway unavailable, cancellation rejected.
    def test_cancel_booking7(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Gateway unavailable.
        self.gateway.refund.side_effect = GatewayUnavailableException()
        # Cancellation rejected.
        self.assertEqual(self.reason_of(self.manager.cancel_booking, info.id), "gateway_unavailable")
        # Booking active, refund status unavailable.
        self.assertEqual((info.status, info.refund_status), ("active", "unavailable"))

    # cancel_booking wraps unexpected failures in ProcessingException.
    def test_cancel_booking8(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Gateway raises an unexpected error.
        self.gateway.refund.side_effect = RuntimeError("boom")
        # The generic exception is raised.
        with self.assertRaises(ProcessingException):
            # Cancel.
            self.manager.cancel_booking(info.id)

    # get_refund_status of a known booking.
    def test_get_refund_status(self):
        # Book a seat.
        info = self.manager.book_seat("c1", "S1", 1, 1)
        # Nothing refunded yet.
        self.assertEqual(self.manager.get_refund_status(info.id), "none")

    # get_refund_status rejects an unknown booking.
    def test_get_refund_status2(self):
        # Unknown booking.
        self.assertEqual(self.reason_of(self.manager.get_refund_status, "nope"), "unknown_booking")

    # get_refund_status wraps unexpected failures in ProcessingException.
    def test_get_refund_status3(self):
        # Corrupt the store so the lookup fails unexpectedly.
        self.manager._bookings = None
        # The generic exception is raised.
        with self.assertRaises(ProcessingException):
            # Read the status.
            self.manager.get_refund_status("B1")
