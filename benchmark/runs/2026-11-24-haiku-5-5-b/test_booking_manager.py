# Standard unittest framework, the runner used by the project test command.
import unittest
# Mock objects that isolate BookingManager from its gateway and logger collaborators.
from unittest import mock
# Times used for screenings and for the cancellation clock.
from datetime import datetime, timedelta
# Class under test and the exception types it raises or interprets.
from seat_booking import (
    # Service class under test.
    BookingManager,
    # Plain entity used to register screenings.
    Screening,
    # Business rejection raised for rule violations.
    BookingRejectedException,
    # Generic wrapper raised at the service boundary.
    ProcessingException,
    # Gateway exception for a transient refund failure.
    TransientRefundException,
    # Gateway exception for a permanent refund failure.
    PermanentRefundException,
    # Gateway exception for an unavailable gateway.
    GatewayUnavailableException,
    # Close the import list.
)


# Mirror test for BookingManager: one test per public method, with collaborators mocked.
class BookingManagerTest(unittest.TestCase):
    # Prepares a mocked logger so tests do not write log output.
    def setUp(self):
        # Start a patch that replaces the module logger with a mock.
        logger_patch = mock.patch("seat_booking.logger")
        # Activate the patch for the duration of the test.
        logger_patch.start()
        # Undo the patch automatically after each test.
        self.addCleanup(logger_patch.stop)
        # Start time shared by the screenings built in these tests.
        self.start_time = datetime(2030, 1, 1, 20, 0)

    # Builds a manager with one registered screening and one active booking on seat 1/1.
    def _build_manager_with_booking(self, gateway):
        # Create the service under test around the supplied mocked gateway.
        manager = BookingManager(gateway)
        # Register a screening with a 2x3 room and a ticket price.
        manager.add_screening(Screening("s1", self.start_time, 2, 3, 12.5))
        # Book seat row 1, seat 1 on that screening so there is a booking to act on.
        manager.book_seat("s1", 1, 1)
        # Return the manager ready for the scenario.
        return manager

    # Registers a screening so that it can be found later.
    def test_add_screening(self):
        # Create the service under test with a mocked gateway.
        manager = BookingManager(mock.Mock())
        # Build the screening to register.
        screening = Screening("s1", self.start_time, 2, 3, 12.5)
        # Register the screening with the manager.
        manager.add_screening(screening)
        # Verify the screening was stored under its identifier.
        self.assertIs(manager.screenings["s1"], screening)

    # Books seats and rejects invalid or already-booked seats.
    def test_book_seat(self):
        # Scenario: a free seat on a registered screening is booked and receives an identifier.
        with self.subTest("books a free seat"):
            # Create the service under test with a mocked gateway.
            manager = BookingManager(mock.Mock())
            # Register a screening with a 2x3 room.
            manager.add_screening(Screening("s1", self.start_time, 2, 3, 12.5))
            # Book row 2, seat 3, which lies inside the room.
            booking_id = manager.book_seat("s1", 2, 3)
            # Verify the first booking receives the identifier "1".
            self.assertEqual(booking_id, "1")
        # Scenario: booking a seat that is already held must be rejected.
        with self.subTest("rejects a seat already booked"):
            # Create the service under test with a mocked gateway.
            manager = self._build_manager_with_booking(mock.Mock())
            # Verify that booking the same seat again raises a rejection.
            with self.assertRaises(BookingRejectedException):
                # Attempt to book seat 1/1 a second time.
                manager.book_seat("s1", 1, 1)
        # Scenario: booking for an unregistered screening must be rejected.
        with self.subTest("rejects an unknown screening"):
            # Create the service under test with a mocked gateway.
            manager = BookingManager(mock.Mock())
            # Verify that booking for an unknown screening raises a rejection.
            with self.assertRaises(BookingRejectedException):
                # Attempt to book on a screening that was never registered.
                manager.book_seat("missing", 1, 1)
        # Scenario: a seat outside the room layout must be rejected.
        with self.subTest("rejects a seat outside the room layout"):
            # Create the service under test with a mocked gateway.
            manager = BookingManager(mock.Mock())
            # Register a screening with a 2x3 room.
            manager.add_screening(Screening("s1", self.start_time, 2, 3, 12.5))
            # Verify that a seat beyond the last row raises a rejection.
            with self.assertRaises(BookingRejectedException):
                # Attempt to book row 3, which does not exist in a two-row room.
                manager.book_seat("s1", 3, 1)

    # Cancels bookings within the cut-off, refunds through the gateway and handles every gateway failure.
    def test_cancel_booking(self):
        # Scenario: a cancellation well before the cut-off refunds the price and releases the seat.
        with self.subTest("refunds and cancels before the cut-off"):
            # Create a mocked gateway that accepts the refund.
            gateway = mock.Mock()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Cancel the booking three hours before the screening starts.
            manager.cancel_booking("1", self.start_time - timedelta(hours=3))
            # Verify the gateway was asked to refund the ticket price once.
            gateway.refund.assert_called_once_with("1", 12.5)
            # Verify the refund status is now REFUNDED.
            self.assertEqual(manager.bookings["1"].refund_status, "REFUNDED")
        # Scenario: a cancellation exactly at the cut-off is still allowed.
        with self.subTest("allows cancellation exactly at the cut-off"):
            # Create a mocked gateway that accepts the refund.
            gateway = mock.Mock()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Cancel exactly two hours before the screening starts.
            manager.cancel_booking("1", self.start_time - timedelta(hours=2))
            # Verify the gateway was asked to refund the ticket price once.
            gateway.refund.assert_called_once_with("1", 12.5)
        # Scenario: a transient failure followed by success is retried and the cancellation completes.
        with self.subTest("retries a transient failure then succeeds"):
            # Create a gateway that fails transiently once and then accepts.
            gateway = mock.Mock()
            # Script the gateway responses: one transient failure, then success.
            gateway.refund.side_effect = [TransientRefundException(), None]
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Cancel the booking well before the cut-off.
            manager.cancel_booking("1", self.start_time - timedelta(hours=3))
            # Verify the gateway was called twice: the failure and the successful retry.
            self.assertEqual(gateway.refund.call_count, 2)
        # Scenario: transient failures that exhaust the retries mark the refund failed and keep the booking active.
        with self.subTest("gives up after three retries on transient failures"):
            # Create a gateway that always fails transiently.
            gateway = mock.Mock()
            # Script the gateway to fail transiently on every call.
            gateway.refund.side_effect = TransientRefundException()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Verify the cancellation is rejected once the retries are exhausted.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation well before the cut-off.
                manager.cancel_booking("1", self.start_time - timedelta(hours=3))
            # Verify the gateway was called once plus three retries.
            self.assertEqual(gateway.refund.call_count, 4)
        # Scenario: a permanent failure marks the refund failed and keeps the booking active.
        with self.subTest("rejects a permanent refund failure"):
            # Create a gateway that fails permanently.
            gateway = mock.Mock()
            # Script the gateway to fail permanently on its first call.
            gateway.refund.side_effect = PermanentRefundException()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Verify the cancellation is rejected with a processing error.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation well before the cut-off.
                manager.cancel_booking("1", self.start_time - timedelta(hours=3))
            # Verify the gateway was called exactly once because permanent failures are not retried.
            self.assertEqual(gateway.refund.call_count, 1)
        # Scenario: an unavailable gateway rejects the cancellation and leaves the refund status untouched.
        with self.subTest("rejects when the gateway is unavailable"):
            # Create a gateway that is unavailable.
            gateway = mock.Mock()
            # Script the gateway to report that it is unavailable.
            gateway.refund.side_effect = GatewayUnavailableException()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Verify the cancellation is rejected with a processing error.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation well before the cut-off.
                manager.cancel_booking("1", self.start_time - timedelta(hours=3))
            # Verify the refund status was not changed because no refund was processed.
            self.assertEqual(manager.bookings["1"].refund_status, "NOT_REQUESTED")
        # Scenario: a cancellation inside the cut-off window is rejected without calling the gateway.
        with self.subTest("rejects a cancellation inside the cut-off"):
            # Create a mocked gateway that must not be called.
            gateway = mock.Mock()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Verify the cancellation is rejected because it is too close to the start.
            with self.assertRaises(BookingRejectedException):
                # Attempt the cancellation one hour and fifty-nine minutes before the start.
                manager.cancel_booking("1", self.start_time - timedelta(hours=1, minutes=59))
            # Verify the gateway was never asked to refund.
            gateway.refund.assert_not_called()
        # Scenario: cancelling an unknown booking is rejected.
        with self.subTest("rejects an unknown booking"):
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(mock.Mock())
            # Verify the cancellation of a missing booking raises a rejection.
            with self.assertRaises(BookingRejectedException):
                # Attempt to cancel a booking identifier that does not exist.
                manager.cancel_booking("missing", self.start_time - timedelta(hours=3))
        # Scenario: cancelling a booking that was already cancelled is rejected.
        with self.subTest("rejects an already cancelled booking"):
            # Create a gateway that accepts the first refund.
            gateway = mock.Mock()
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(gateway)
            # Cancel the booking once successfully.
            manager.cancel_booking("1", self.start_time - timedelta(hours=3))
            # Verify a second cancellation of the same booking raises a rejection.
            with self.assertRaises(BookingRejectedException):
                # Attempt to cancel the same booking again.
                manager.cancel_booking("1", self.start_time - timedelta(hours=3))

    # Exposes the refund status of a booking and rejects unknown bookings.
    def test_get_refund_status(self):
        # Scenario: a booking that has not been refunded reports NOT_REQUESTED.
        with self.subTest("reports the status of an active booking"):
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(mock.Mock())
            # Verify the refund status of the active booking is NOT_REQUESTED.
            self.assertEqual(manager.get_refund_status("1"), "NOT_REQUESTED")
        # Scenario: asking for the status of an unknown booking is rejected.
        with self.subTest("rejects an unknown booking"):
            # Create the service under test with one active booking.
            manager = self._build_manager_with_booking(mock.Mock())
            # Verify the status request for a missing booking raises a rejection.
            with self.assertRaises(BookingRejectedException):
                # Attempt to read the status of a booking identifier that does not exist.
                manager.get_refund_status("missing")
