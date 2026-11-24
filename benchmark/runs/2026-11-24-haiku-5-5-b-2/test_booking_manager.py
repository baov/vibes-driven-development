# Import unittest to run the test cases.
import unittest
# Import datetime and timedelta to build screening times and the cancellation cut-off.
from datetime import datetime, timedelta
# Import Mock and patch to replace the collaborators with test doubles.
from unittest.mock import Mock, patch
# Import the class under test, its status constants and the exceptions it raises or receives.
from seat_booking.booking_manager import (
    ACTIVE,
    CANCELLED,
    REFUND_FAILED,
    REFUND_NONE,
    REFUND_REFUNDED,
    BookingManager,
    PaymentGatewayUnavailableError,
    PermanentPaymentError,
    ProcessingException,
    TransientPaymentError,
)


# Test case for BookingManager: one test per method, with the gateway, screening and logger mocked.
class BookingManagerTest(unittest.TestCase):
    # Build a manager with mocked collaborators before each test.
    def setUp(self):
        # Fixed start time of the mocked screening.
        self.start_time = datetime(2030, 1, 1, 20, 0)
        # Mocked payment gateway whose behaviour each test sets through side_effect.
        self.gateway = Mock()
        # Mocked screening exposing the attributes the manager reads.
        self.screening = Mock(screening_id="s1", start_time=self.start_time, price=12.5, room=Mock(rows=3, seats_per_row=4))
        # Patch the module logger so logs stay out of the test output.
        patcher = patch("seat_booking.booking_manager.logger")
        # Start the patch so the logger is replaced for the duration of the test.
        self.logger = patcher.start()
        # Undo the patch once the test finishes.
        self.addCleanup(patcher.stop)
        # Create the manager under test around the mocked gateway.
        self.manager = BookingManager(self.gateway)

    # Test the constructor: building a manager yields a usable instance.
    def test___init__(self):
        # Build a fresh manager around the gateway.
        manager = BookingManager(self.gateway)
        # Check the constructor returned an instance.
        self.assertIsNotNone(manager)

    # Test book_seat: a free seat inside the room is booked as active.
    def test_book_seat(self):
        # Book a seat that is free and inside the room.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Check the new booking holds its seat.
        self.assertEqual(booking.status, ACTIVE)

    # Test book_seat: a seat outside the room layout is rejected.
    def test_book_seat2(self):
        # Ask for row 4, which does not exist in a room with 3 rows.
        with self.assertRaises(ProcessingException):
            # Attempt the out-of-room booking.
            self.manager.book_seat(self.screening, 4, 1, "c1")

    # Test book_seat: a seat already held by an active booking is rejected.
    def test_book_seat3(self):
        # Book the seat once so it is held.
        self.manager.book_seat(self.screening, 1, 1, "c1")
        # Check a second booking of the same seat is rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that is already taken.
            self.manager.book_seat(self.screening, 1, 1, "c2")

    # Test book_seat: a seat freed by a cancellation can be booked again.
    def test_book_seat4(self):
        # Book the seat so it is held.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Cancel it well before the screening so the seat is released.
        self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))
        # Book the same seat again.
        rebooked = self.manager.book_seat(self.screening, 1, 1, "c2")
        # Check the second booking holds the seat.
        self.assertEqual(rebooked.status, ACTIVE)

    # Test cancel_booking: a cancellation exactly at the cut-off refunds the price and cancels the booking.
    def test_cancel_booking(self):
        # Book a seat to cancel later.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Cancel exactly two hours before the screening, which is still allowed.
        cancelled = self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=2))
        # Check the gateway was asked to refund the price once.
        self.gateway.refund.assert_called_once_with(booking.booking_id, 12.5)
        # Check the refund is recorded as completed.
        self.assertEqual(cancelled.refund_status, REFUND_REFUNDED)

    # Test cancel_booking: an unknown booking id is rejected.
    def test_cancel_booking2(self):
        # Check cancelling a booking that was never made is rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to cancel an unknown booking.
            self.manager.cancel_booking(999, self.start_time - timedelta(hours=3))

    # Test cancel_booking: a booking that is already cancelled is rejected.
    def test_cancel_booking3(self):
        # Book a seat and cancel it once.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Cancel the booking so it is no longer active.
        self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))
        # Check cancelling it a second time is rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the second cancellation.
            self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))

    # Test cancel_booking: a cancellation less than two hours before the screening is rejected.
    def test_cancel_booking4(self):
        # Book a seat to attempt a late cancellation on.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Check a cancellation one second too late is rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the late cancellation.
            self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=2) + timedelta(seconds=1))

    # Test cancel_booking: a transient refund failure is retried and succeeds on a later attempt.
    def test_cancel_booking5(self):
        # Book a seat to cancel.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Make the first refund fail transiently and the second succeed.
        self.gateway.refund.side_effect = [TransientPaymentError(), None]
        # Cancel the booking while the refund is still being retried.
        cancelled = self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))
        # Check the gateway was called twice, once per attempt.
        self.assertEqual(self.gateway.refund.call_count, 2)
        # Check the booking ended up cancelled with the refund completed.
        self.assertEqual((cancelled.status, cancelled.refund_status), (CANCELLED, REFUND_REFUNDED))

    # Test cancel_booking: transient refund failures on every attempt leave the booking active with a failed refund.
    def test_cancel_booking6(self):
        # Book a seat to cancel.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Make every refund attempt fail transiently.
        self.gateway.refund.side_effect = TransientPaymentError()
        # Cancel the booking, which should exhaust its retries.
        result = self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))
        # Check the gateway was called once plus three retries.
        self.assertEqual(self.gateway.refund.call_count, 4)
        # Check the booking stays active with the refund marked as failed.
        self.assertEqual((result.status, result.refund_status), (ACTIVE, REFUND_FAILED))

    # Test cancel_booking: a permanent refund refusal stops retrying and leaves the booking active.
    def test_cancel_booking7(self):
        # Book a seat to cancel.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Make the gateway refuse the refund permanently.
        self.gateway.refund.side_effect = PermanentPaymentError()
        # Cancel the booking, which should not be retried.
        result = self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))
        # Check the gateway was called exactly once.
        self.assertEqual(self.gateway.refund.call_count, 1)
        # Check the booking stays active with the refund marked as failed.
        self.assertEqual((result.status, result.refund_status), (ACTIVE, REFUND_FAILED))

    # Test cancel_booking: an unavailable gateway rejects the cancellation and leaves the booking untouched.
    def test_cancel_booking8(self):
        # Book a seat to cancel.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Make the gateway unreachable.
        self.gateway.refund.side_effect = PaymentGatewayUnavailableError()
        # Check the cancellation is rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation against the unavailable gateway.
            self.manager.cancel_booking(booking.booking_id, self.start_time - timedelta(hours=3))
        # Check the refund status was not changed by the rejected cancellation.
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_NONE)

    # Test get_refund_status: a booking that was never refunded reports no refund yet.
    def test_get_refund_status(self):
        # Book a seat so there is a booking to inspect.
        booking = self.manager.book_seat(self.screening, 1, 1, "c1")
        # Check no refund has been made yet.
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_NONE)

    # Test get_refund_status: an unknown booking id is rejected.
    def test_get_refund_status2(self):
        # Check asking for the refund status of an unknown booking is rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the lookup for an unknown booking.
            self.manager.get_refund_status(999)
