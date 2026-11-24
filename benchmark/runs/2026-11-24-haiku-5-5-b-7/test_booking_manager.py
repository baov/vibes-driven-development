# Import unittest, the standard test framework used by the project's test command.
import unittest
# Import mock to stand in for the payment gateway, the clock and the screenings.
from unittest import mock
# Import datetime for the mocked start times and clock values.
from datetime import datetime
# Import the class under test and the exceptions it raises or consumes.
from seat_booking import (
    # Class under test.
    BookingManager,
    # Generic exception the manager raises to its callers.
    ProcessingException,
    # Gateway exception for transient failures.
    GatewayTransientError,
    # Gateway exception for permanent failures.
    GatewayPermanentError,
    # Gateway exception for an outage.
    GatewayUnavailableError,
)


# Mirror test for BookingManager: one test file per class, one test method per public method.
class BookingManagerTest(unittest.TestCase):
    # Build a manager with a mocked gateway, a fixed clock and one mocked screening.
    def setUp(self):
        # Mocked payment gateway; refunds succeed unless a test changes its behaviour.
        self.gateway = mock.Mock()
        # Mocked clock fixed at 17:00, which is three hours before the screening.
        self.clock = mock.Mock(return_value=datetime(2026, 12, 1, 17, 0))
        # Mocked screening starting at 20:00 with a 3x5 room and a price of 1200 cents.
        self.screening = mock.Mock(
            start=datetime(2026, 12, 1, 20, 0),
            price_cents=1200,
            room=mock.Mock(rows=3, seats_per_row=5),
        )
        # Manager under test with the single mocked screening registered under "s1".
        self.manager = BookingManager({"s1": self.screening}, self.gateway, self.clock)

    # Constructing the manager succeeds with the mocked collaborators.
    def test___init__(self):
        # The manager built in setUp exists.
        self.assertIsNotNone(self.manager)

    # Booking a free seat returns a booking identifier.
    def test_book_seat(self):
        # Book seat 1-1 of the screening.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # The identifier is a non-empty string.
        self.assertTrue(booking_id)

    # Booking for an unknown screening is rejected.
    def test_book_seat2(self):
        # The unknown screening must raise the generic exception.
        with self.assertRaises(ProcessingException):
            # Attempt the booking for a screening that does not exist.
            self.manager.book_seat("missing", 1, 1)

    # Booking a seat outside the room grid is rejected.
    def test_book_seat3(self):
        # Row 4 does not exist in a room with three rows.
        with self.assertRaises(ProcessingException):
            # Attempt the booking of the nonexistent row.
            self.manager.book_seat("s1", 4, 1)

    # Booking a seat that is already held is rejected.
    def test_book_seat4(self):
        # Hold seat 2-3 once.
        self.manager.book_seat("s1", 2, 3)
        # Holding the same seat again must raise.
        with self.assertRaises(ProcessingException):
            # Attempt the second booking of the same seat.
            self.manager.book_seat("s1", 2, 3)

    # A seat released by a cancellation can be booked again.
    def test_book_seat5(self):
        # Hold seat 1-2 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 2)
        # Cancel it so the seat is released.
        self.manager.cancel_booking(booking_id)
        # Booking the released seat again must succeed without raising.
        self.manager.book_seat("s1", 1, 2)

    # The refund status of a new booking is "none".
    def test_get_refund_status(self):
        # Hold seat 1-1 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # Read the refund status of the new booking.
        status = self.manager.get_refund_status(booking_id)
        # No refund has been requested yet.
        self.assertEqual(status, "none")

    # Asking for the refund status of an unknown booking is rejected.
    def test_get_refund_status2(self):
        # The unknown booking must raise the generic exception.
        with self.assertRaises(ProcessingException):
            # Attempt to read the status of a booking that does not exist.
            self.manager.get_refund_status("missing")

    # A cancellation before the cutoff refunds the price and marks the refund as refunded.
    def test_cancel_booking(self):
        # Hold seat 1-1 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # Cancel the booking while the cutoff has not passed.
        self.manager.cancel_booking(booking_id)
        # The gateway was asked to refund the screening price against the booking.
        self.gateway.refund.assert_called_once_with(booking_id, 1200)
        # The booking now reports a refunded status.
        self.assertEqual(self.manager.get_refund_status(booking_id), "refunded")

    # Cancelling an unknown booking is rejected.
    def test_cancel_booking2(self):
        # The unknown booking must raise the generic exception.
        with self.assertRaises(ProcessingException):
            # Attempt to cancel a booking that does not exist.
            self.manager.cancel_booking("missing")

    # Cancelling a booking that is already cancelled is rejected.
    def test_cancel_booking3(self):
        # Hold and cancel seat 1-1 once.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # Cancel the booking the first time.
        self.manager.cancel_booking(booking_id)
        # The second cancellation must raise.
        with self.assertRaises(ProcessingException):
            # Attempt to cancel the same booking again.
            self.manager.cancel_booking(booking_id)

    # Cancelling after the cutoff is rejected and no refund is requested.
    def test_cancel_booking4(self):
        # Hold seat 1-1 while the clock is still before the cutoff.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # Move the clock one minute past the cutoff, which is 18:00.
        self.clock.return_value = datetime(2026, 12, 1, 18, 1)
        # Attempting the cancellation after the cutoff must raise.
        with self.assertRaises(ProcessingException):
            # Attempt the late cancellation.
            self.manager.cancel_booking(booking_id)
        # The gateway must not have been asked for any refund.
        self.gateway.refund.assert_not_called()

    # A transient gateway failure is retried and the cancellation then succeeds.
    def test_cancel_booking5(self):
        # The first refund attempt fails transiently and the second succeeds.
        self.gateway.refund.side_effect = [GatewayTransientError(), None]
        # Hold seat 1-1 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # Cancel the booking, which triggers the retry.
        self.manager.cancel_booking(booking_id)
        # The gateway was called twice: the failure and the retry.
        self.assertEqual(self.gateway.refund.call_count, 2)

    # Transient failures on every attempt exhaust the retries, mark the refund failed and keep the booking active.
    def test_cancel_booking6(self):
        # Every refund attempt fails transiently.
        self.gateway.refund.side_effect = GatewayTransientError()
        # Hold seat 1-1 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # The cancellation must raise once the retries are exhausted.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation that cannot be refunded.
            self.manager.cancel_booking(booking_id)
        # The gateway was called for the initial attempt plus three retries.
        self.assertEqual(self.gateway.refund.call_count, 4)
        # The refund status records the failure.
        self.assertEqual(self.manager.get_refund_status(booking_id), "failed")

    # A permanent gateway failure marks the refund failed and leaves the booking active, so a later cancellation can succeed.
    def test_cancel_booking7(self):
        # The first refund is refused permanently; the second succeeds.
        self.gateway.refund.side_effect = [GatewayPermanentError(), None]
        # Hold seat 1-1 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # The first cancellation must raise because the refund was refused.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation that the gateway refuses.
            self.manager.cancel_booking(booking_id)
        # The refund status records the permanent failure.
        self.assertEqual(self.manager.get_refund_status(booking_id), "failed")
        # The booking is still active, so cancelling it again succeeds.
        self.manager.cancel_booking(booking_id)

    # An unavailable gateway rejects the cancellation and leaves the refund status untouched.
    def test_cancel_booking8(self):
        # The gateway is unavailable for every call.
        self.gateway.refund.side_effect = GatewayUnavailableError()
        # Hold seat 1-1 and keep its identifier.
        booking_id = self.manager.book_seat("s1", 1, 1)
        # The cancellation must be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt the cancellation while the gateway is down.
            self.manager.cancel_booking(booking_id)
        # No refund was recorded because none succeeded or was refused.
        self.assertEqual(self.manager.get_refund_status(booking_id), "none")
