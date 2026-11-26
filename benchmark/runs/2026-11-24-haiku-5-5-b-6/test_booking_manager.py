# Tests for BookingManager, mirroring seat_booking/booking_manager.py.
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

# Import the class under test and its collaborators' contracts.
from seat_booking.booking_manager import ACTIVE, CANCELLED, REFUND_FAILED, REFUND_REFUNDED, BookingManager, ProcessingException
from seat_booking.payment_gateway import PaymentGateway, PaymentGatewayUnavailableError, PermanentPaymentError, TransientPaymentError

# Fixed current time used by the mocked clock.
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
# Fixed screening start time, more than two hours after NOW.
START = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)


# Test class mirroring BookingManager; one test per method, with numbered variants for other scenarios.
class BookingManagerTest(unittest.TestCase):
    # Build a fresh manager with mocked gateway, clock and screening before each test.
    def setUp(self):
        # Mock the payment gateway so refunds can be scripted and counted.
        self.gateway = Mock(spec=PaymentGateway)
        # Mock the clock so the current time is fixed.
        self.clock = Mock(return_value=NOW)
        # Mock a screening carrying the attributes the manager reads.
        self.screening = Mock(screening_id="s1", start_time=START, rows=3, seats_per_row=4, price_cents=1200)
        # Build the manager under test with the mocked collaborators.
        self.manager = BookingManager(self.gateway, self.clock)
        # Register the mocked screening with the manager.
        self.manager.add_screening(self.screening)

    # Check that the constructor accepts the gateway and clock.
    def test___init__(self):
        # Build a manager with the default clock.
        manager = BookingManager(self.gateway)
        # Check that an instance was created.
        self.assertIsInstance(manager, BookingManager)

    # Check that a registered screening can be booked.
    def test_add_screening(self):
        # Book a seat in the registered screening.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Check that the booking was issued for that screening.
        self.assertEqual(booking.screening_id, "s1")

    # Check that a free seat is booked as an active booking.
    def test_book_seat(self):
        # Book a free seat in the registered screening.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Check that the new booking is active.
        self.assertEqual(booking.status, ACTIVE)

    # Check that booking a seat already held is rejected.
    def test_book_seat2(self):
        # Hold seat 1-1 with a first booking.
        self.manager.book_seat("s1", "c1", 1, 1)
        # Expect a second booking of the same seat to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that is already held.
            self.manager.book_seat("s1", "c2", 1, 1)

    # Check that booking an unknown screening is rejected.
    def test_book_seat3(self):
        # Expect booking a screening that was never registered to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to book in an unknown screening.
            self.manager.book_seat("unknown", "c1", 1, 1)

    # Check that booking a seat outside the room is rejected.
    def test_book_seat4(self):
        # Expect a seat number beyond the room's columns to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to book seat 5 in a room with four seats per row.
            self.manager.book_seat("s1", "c1", 1, 5)

    # Check that a successful cancellation refunds the screening price.
    def test_cancel_booking(self):
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Cancel the booking.
        self.manager.cancel_booking(booking.booking_id)
        # Check that the gateway was asked to refund the price once.
        self.gateway.refund.assert_called_once_with(booking.booking_id, 1200)

    # Check that transient gateway failures are retried until one succeeds.
    def test_cancel_booking2(self):
        # Script two transient failures followed by success.
        self.gateway.refund.side_effect = [TransientPaymentError(), TransientPaymentError(), None]
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Cancel the booking.
        self.manager.cancel_booking(booking.booking_id)
        # Check that three refund attempts were made.
        self.assertEqual(self.gateway.refund.call_count, 3)

    # Check that transient failures stop after the first attempt plus three retries.
    def test_cancel_booking3(self):
        # Script transient failures on every attempt.
        self.gateway.refund.side_effect = TransientPaymentError()
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Expect the cancellation to be rejected once retries run out.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation.
            self.manager.cancel_booking(booking.booking_id)
        # Check that exactly four attempts were made.
        self.assertEqual(self.gateway.refund.call_count, 4)

    # Check that a permanent gateway failure rejects the cancellation without retrying.
    def test_cancel_booking4(self):
        # Script a permanent failure.
        self.gateway.refund.side_effect = PermanentPaymentError()
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Expect the cancellation to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation.
            self.manager.cancel_booking(booking.booking_id)
        # Check that the gateway was called once with no retry.
        self.assertEqual(self.gateway.refund.call_count, 1)

    # Check that an unavailable gateway rejects the cancellation without retrying.
    def test_cancel_booking5(self):
        # Script an unavailable gateway.
        self.gateway.refund.side_effect = PaymentGatewayUnavailableError()
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Expect the cancellation to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation.
            self.manager.cancel_booking(booking.booking_id)
        # Check that the gateway was called once with no retry.
        self.assertEqual(self.gateway.refund.call_count, 1)

    # Check that cancelling an unknown booking is rejected without touching the gateway.
    def test_cancel_booking6(self):
        # Expect cancelling an id that was never issued to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to cancel an unknown booking.
            self.manager.cancel_booking("missing")
        # Check that no refund was attempted.
        self.gateway.refund.assert_not_called()

    # Check that cancelling an already cancelled booking is rejected.
    def test_cancel_booking7(self):
        # Hold a seat and cancel it successfully.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Cancel the booking once.
        self.manager.cancel_booking(booking.booking_id)
        # Expect a second cancellation to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to cancel the same booking again.
            self.manager.cancel_booking(booking.booking_id)

    # Check that cancelling inside the two-hour window is rejected without a refund.
    def test_cancel_booking8(self):
        # Set the clock to one hour before the start, inside the deadline.
        self.clock.return_value = START - timedelta(hours=1)
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Expect the late cancellation to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the late cancellation.
            self.manager.cancel_booking(booking.booking_id)
        # Check that no refund was attempted.
        self.gateway.refund.assert_not_called()

    # Check that cancelling exactly two hours before the start is still allowed.
    def test_cancel_booking9(self):
        # Set the clock to exactly two hours before the start.
        self.clock.return_value = START - timedelta(hours=2)
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Cancel the booking at the deadline.
        self.manager.cancel_booking(booking.booking_id)
        # Check that the refund was attempted.
        self.gateway.refund.assert_called_once_with(booking.booking_id, 1200)

    # Check that the refund status of a refunded booking is REFUNDED.
    def test_get_refund_status(self):
        # Hold a seat and cancel it with a successful refund.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Cancel the booking.
        self.manager.cancel_booking(booking.booking_id)
        # Check the reported refund status.
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_REFUNDED)

    # Check that a permanently failed refund is reported as FAILED and the booking stays active.
    def test_get_refund_status2(self):
        # Script a permanent refund failure.
        self.gateway.refund.side_effect = PermanentPaymentError()
        # Hold a seat so there is a booking to cancel.
        booking = self.manager.book_seat("s1", "c1", 1, 1)
        # Attempt the cancellation, which the gateway refuses.
        with self.assertRaises(ProcessingException):
            # Cancel the booking.
            self.manager.cancel_booking(booking.booking_id)
        # Check the reported refund status.
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_FAILED)

    # Check that querying the refund status of an unknown booking is rejected.
    def test_get_refund_status3(self):
        # Expect a query for an unknown booking to be rejected.
        with self.assertRaises(ProcessingException):
            # Query the unknown booking.
            self.manager.get_refund_status("missing")
