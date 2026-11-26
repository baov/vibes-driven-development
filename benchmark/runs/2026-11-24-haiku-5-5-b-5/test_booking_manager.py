# Standard library unittest framework and mocks for collaborators.
import unittest
# Mock provides the gateway and clock collaborators; patch replaces the module logger.
from unittest.mock import Mock, patch
# Time types used to build the screening and clock values.
from datetime import datetime, timedelta

# Class under test and the collaborators it uses, imported from the production package.
from seat_booking import (
    BookingManager,
    CANCELLATION_CUTOFF,
    GatewayUnavailableError,
    PaymentGateway,
    PermanentGatewayError,
    ProcessingException,
    Room,
    Screening,
    TransientGatewayError,
)

# Fixed current time supplied by the mocked clock.
NOW = datetime(2026, 11, 24, 12, 0)
# Start time far enough away that a cancellation is allowed.
LATER_START = NOW + timedelta(days=1)
# Ticket price used by the screening under test, in cents.
PRICE_CENTS = 1200


# Mirrors the BookingManager production class.
class BookingManagerTest(unittest.TestCase):
    # Builds the mocked collaborators and the manager under test for every test.
    def setUp(self):
        # Patch the module logger so test output stays readable.
        patcher = patch("seat_booking.logger")
        # Start the patch for this test.
        self.logger = patcher.start()
        # Undo the patch after the test finishes.
        self.addCleanup(patcher.stop)
        # Mocked payment gateway collaborator.
        self.gateway = Mock(spec=PaymentGateway)
        # Mocked clock fixed at NOW.
        self.clock = Mock(return_value=NOW)
        # Manager under test wired to the mocks.
        self.manager = BookingManager(self.gateway, self.clock)
        # Plain data screening with a 2 x 3 room, starting later than the cutoff.
        self.screening = Screening("S1", LATER_START, Room(rows=2, seats_per_row=3), PRICE_CENTS)
        # Register the screening with the manager.
        self.manager.add_screening(self.screening)

    # Builds an independent manager with its own gateway and clock, for a scenario.
    def _build_manager(self, gateway, clock=None):
        # Create a manager using the given gateway and a clock that defaults to NOW.
        manager = BookingManager(gateway, clock or Mock(return_value=NOW))
        # Register the shared screening with that manager.
        manager.add_screening(self.screening)
        # Return the ready manager.
        return manager

    # Tests the constructor, which stores the injected gateway.
    def test___init__(self):
        # Verify the manager keeps the gateway it was given.
        self.assertIs(self.manager.gateway, self.gateway)

    # Tests add_screening, which registers a screening under its id.
    def test_add_screening(self):
        # Verify the screening is now known to the manager.
        self.assertIn("S1", self.manager.screenings)

    # Tests book_seat across success and each rejection.
    def test_book_seat(self):
        # Scenario: a free seat inside the room is booked as active.
        with self.subTest("books a free seat"):
            # Book seat row 2, seat 3 of the screening.
            booking = self.manager.book_seat("S1", 2, 3)
            # Verify the new booking is active.
            self.assertEqual(booking.status, "active")
        # Scenario: an unknown screening is rejected.
        with self.subTest("rejects unknown screening"):
            # Verify booking against a missing screening raises.
            with self.assertRaises(ProcessingException):
                # Attempt the booking.
                self.manager.book_seat("X", 1, 1)
        # Scenario: a seat outside the room layout is rejected.
        with self.subTest("rejects seat outside room"):
            # Verify a row beyond the room raises.
            with self.assertRaises(ProcessingException):
                # Attempt the booking.
                self.manager.book_seat("S1", 3, 1)
        # Scenario: a seat already held by an active booking is rejected.
        with self.subTest("rejects already booked seat"):
            # Hold seat row 1, seat 1 first.
            self.manager.book_seat("S1", 1, 1)
            # Verify the second booking of the same seat raises.
            with self.assertRaises(ProcessingException):
                # Attempt the duplicate booking.
                self.manager.book_seat("S1", 1, 1)

    # Tests cancel_booking across success, rejections, and every gateway outcome.
    def test_cancel_booking(self):
        # Scenario: a successful refund cancels the booking and marks it refunded.
        with self.subTest("cancels and refunds"):
            # Fresh gateway whose refund succeeds.
            gateway = Mock(spec=PaymentGateway)
            # Build a manager around that gateway.
            manager = self._build_manager(gateway)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Cancel the booking.
            result = manager.cancel_booking(booking.booking_id)
            # Verify the booking is cancelled.
            self.assertEqual(result.status, "cancelled")
        # Scenario: a booking exactly at the cutoff is still allowed to cancel.
        with self.subTest("allows cancellation exactly at the cutoff"):
            # Clock set exactly CANCELLATION_CUTOFF before the screening starts.
            clock = Mock(return_value=LATER_START - CANCELLATION_CUTOFF)
            # Build a manager whose clock is at the cutoff.
            manager = self._build_manager(Mock(spec=PaymentGateway), clock)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Cancel the booking at the cutoff.
            result = manager.cancel_booking(booking.booking_id)
            # Verify the cancellation went through.
            self.assertEqual(result.status, "cancelled")
        # Scenario: an unknown booking is rejected.
        with self.subTest("rejects unknown booking"):
            # Verify cancelling a missing booking raises.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                self.manager.cancel_booking("B99")
        # Scenario: cancelling an already cancelled booking is rejected.
        with self.subTest("rejects already cancelled booking"):
            # Use a fresh manager so the earlier cancellations do not interfere.
            manager = self._build_manager(Mock(spec=PaymentGateway))
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Cancel it once successfully.
            manager.cancel_booking(booking.booking_id)
            # Verify the second cancellation raises.
            with self.assertRaises(ProcessingException):
                # Attempt the second cancellation.
                manager.cancel_booking(booking.booking_id)
        # Scenario: a cancellation after the cutoff is rejected.
        with self.subTest("rejects cancellation inside the cutoff"):
            # Clock one hour before the screening, inside the cutoff.
            clock = Mock(return_value=LATER_START - timedelta(hours=1))
            # Build a manager whose clock is inside the cutoff.
            manager = self._build_manager(Mock(spec=PaymentGateway), clock)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Verify the late cancellation raises.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)
        # Scenario: a transient failure is retried and then succeeds.
        with self.subTest("retries transient failure then succeeds"):
            # Gateway fails once transiently, then succeeds.
            gateway = Mock(spec=PaymentGateway)
            # Configure the two refund outcomes in order.
            gateway.refund.side_effect = [TransientGatewayError(), None]
            # Build a manager around that gateway.
            manager = self._build_manager(gateway)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Cancel the booking.
            result = manager.cancel_booking(booking.booking_id)
            # Verify the refund was retried and recorded as refunded.
            self.assertEqual(result.refund_status, "refunded")
        # Scenario: repeated transient failures exhaust the retries and leave the booking active.
        with self.subTest("gives up after three retries and stays active"):
            # Gateway fails transiently on every attempt.
            gateway = Mock(spec=PaymentGateway)
            # Configure one transient error per allowed attempt (first try plus three retries).
            gateway.refund.side_effect = [TransientGatewayError()] * 4
            # Build a manager around that gateway.
            manager = self._build_manager(gateway)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Cancel the booking.
            result = manager.cancel_booking(booking.booking_id)
            # Verify the booking stays active with a failed refund.
            self.assertEqual(result.status, "active")
        # Scenario: a permanent failure leaves the booking active without retrying.
        with self.subTest("permanent failure keeps booking active"):
            # Gateway fails permanently on the first attempt.
            gateway = Mock(spec=PaymentGateway)
            # Configure a permanent error for the refund.
            gateway.refund.side_effect = PermanentGatewayError()
            # Build a manager around that gateway.
            manager = self._build_manager(gateway)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Cancel the booking.
            result = manager.cancel_booking(booking.booking_id)
            # Verify the refund is recorded as failed.
            self.assertEqual(result.refund_status, "failed")
        # Scenario: an unavailable gateway rejects the cancellation and leaves the booking untouched.
        with self.subTest("unavailable gateway rejects cancellation"):
            # Gateway is unavailable for the refund.
            gateway = Mock(spec=PaymentGateway)
            # Configure an unavailable error for the refund.
            gateway.refund.side_effect = GatewayUnavailableError()
            # Build a manager around that gateway.
            manager = self._build_manager(gateway)
            # Hold a seat to cancel.
            booking = manager.book_seat("S1", 1, 1)
            # Verify the cancellation is rejected.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)

    # Tests get_refund_status across a known booking and an unknown one.
    def test_get_refund_status(self):
        # Scenario: a fresh booking reports no refund yet.
        with self.subTest("reports status of known booking"):
            # Hold a seat.
            booking = self.manager.book_seat("S1", 1, 1)
            # Verify the status of a booking with no refund attempted.
            self.assertEqual(self.manager.get_refund_status(booking.booking_id), "none")
        # Scenario: an unknown booking is rejected.
        with self.subTest("rejects unknown booking"):
            # Verify querying a missing booking raises.
            with self.assertRaises(ProcessingException):
                # Attempt the query.
                self.manager.get_refund_status("B99")
