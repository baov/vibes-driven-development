# Standard logging module, silenced for this test module.
import logging
# Standard unittest framework.
import unittest
# Timestamps for the fixed clock and screening start.
from datetime import datetime, timedelta, timezone
# Mock stands in for every collaborator: gateway, clock and screenings.
from unittest.mock import Mock

# Production classes and exceptions under test.
from seat_booking import (
    BookingManager,
    BookingStatus,
    GatewayPermanentError,
    GatewayTransientError,
    GatewayUnavailableError,
    ProcessingException,
    RefundStatus,
)

# Fixed start time of the mocked screening.
START = datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc)
# Price of the mocked screening in cents.
PRICE = 1200


# Turns off log output for this module so test runs stay readable.
def setUpModule():
    # Raise the logging threshold above every level.
    logging.disable(logging.CRITICAL)


# Restores log output once this module's tests have finished.
def tearDownModule():
    # Reset the logging threshold to its default.
    logging.disable(logging.NOTSET)


# Builds a mocked screening of a 5 by 10 room.
def make_screening(screening_id="s1"):
    # Mock the screening entity with its identifier, start time and price.
    screening = Mock(screening_id=screening_id, start_time=START, price_cents=PRICE)
    # Attach a mocked room with five rows of ten seats.
    screening.room = Mock(rows=5, seats_per_row=10)
    # Return the mocked screening.
    return screening


# Builds a manager with a mocked gateway and a fixed clock, and registers one screening.
def make_manager(gateway=None, now=START - timedelta(days=1)):
    # Use a fresh mocked gateway when none is given.
    gateway = gateway or Mock()
    # Fix the clock at the given instant.
    clock = Mock(return_value=now)
    # Build the manager with the mocked collaborators.
    manager = BookingManager(gateway, clock=clock)
    # Register the mocked screening.
    manager.add_screening(make_screening())
    # Return the manager and its gateway so tests can inspect calls.
    return manager, gateway


# Tests for the BookingManager class, one test per public method.
class TestBookingManager(unittest.TestCase):

    # Verifies the default clock returns a timezone-aware time.
    def test___init__(self):
        # Build a manager without an explicit clock.
        manager = BookingManager(Mock())
        # Read the default clock.
        now = manager._clock()
        # Check the default time carries a timezone.
        self.assertIsNotNone(now.tzinfo)

    # Verifies a registered screening can be booked.
    def test_add_screening(self):
        # Build a manager with no screenings.
        manager = BookingManager(Mock())
        # Register a mocked screening.
        manager.add_screening(make_screening("s2"))
        # Book a seat in the newly registered screening.
        booking = manager.book_seat("client-1", "s2", 1, 1)
        # Check the booking points at that screening.
        self.assertEqual(booking.screening_id, "s2")

    # Verifies booking outcomes: success, unknown screening, nonexistent seat, held seat, freed seat.
    def test_book_seat(self):
        # Scenario: a free seat inside the room is booked as active.
        with self.subTest("free seat"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Book a free seat.
            booking = manager.book_seat("client-1", "s1", 2, 3)
            # Check the new booking is active.
            self.assertIs(booking.status, BookingStatus.ACTIVE)

        # Scenario: an unregistered screening is rejected.
        with self.subTest("unknown screening"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Expect the booking to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book in an unknown screening.
                manager.book_seat("client-1", "missing", 1, 1)

        # Scenario: a seat outside the room is rejected.
        with self.subTest("nonexistent seat"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Expect the booking to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book a row beyond the room.
                manager.book_seat("client-1", "s1", 6, 1)

        # Scenario: a seat already held by an active booking is rejected.
        with self.subTest("seat already booked"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Hold the seat once.
            manager.book_seat("client-1", "s1", 1, 1)
            # Expect the second attempt to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to hold the same seat again.
                manager.book_seat("client-2", "s1", 1, 1)

        # Scenario: a seat freed by a cancellation can be booked again.
        with self.subTest("seat freed by cancellation"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Hold the seat.
            first = manager.book_seat("client-1", "s1", 1, 1)
            # Cancel that booking to release the seat.
            manager.cancel_booking(first.booking_id)
            # Book the same seat again.
            second = manager.book_seat("client-2", "s1", 1, 1)
            # Check the new booking is active.
            self.assertIs(second.status, BookingStatus.ACTIVE)

    # Verifies a booking can be fetched by id and that unknown ids are rejected.
    def test_get_booking(self):
        # Scenario: a known booking is returned.
        with self.subTest("known booking"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Create a booking to fetch.
            created = manager.book_seat("client-1", "s1", 1, 1)
            # Fetch it by id.
            fetched = manager.get_booking(created.booking_id)
            # Check the fetched booking is the one created.
            self.assertEqual(fetched.client_id, "client-1")

        # Scenario: an unknown id is rejected.
        with self.subTest("unknown booking"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Expect the lookup to be rejected.
            with self.assertRaises(ProcessingException):
                # Look up an id that was never issued.
                manager.get_booking(999)

    # Verifies cancellation outcomes: refunds, retries, failures, cut-off and invalid bookings.
    def test_cancel_booking(self):
        # Scenario: an accepted refund cancels the booking and marks it refunded.
        with self.subTest("refund accepted"):
            # Build a fresh manager with a gateway that accepts refunds.
            manager, gateway = make_manager()
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Cancel the booking.
            manager.cancel_booking(booking.booking_id)
            # Check the gateway was asked to refund the full price.
            gateway.refund.assert_called_once_with(booking.booking_id, PRICE)

        # Scenario: a transient failure is retried and the second attempt succeeds.
        with self.subTest("transient failure then success"):
            # Build a fresh manager.
            manager, gateway = make_manager()
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Fail once transiently, then accept.
            gateway.refund.side_effect = [GatewayTransientError(), None]
            # Cancel the booking.
            manager.cancel_booking(booking.booking_id)
            # Check the refund was attempted twice.
            self.assertEqual(gateway.refund.call_count, 2)

        # Scenario: transient failures exhaust the retry budget of three retries, so four attempts in total.
        with self.subTest("transient failures exhaust retries"):
            # Build a fresh manager.
            manager, gateway = make_manager()
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Fail transiently on every attempt.
            gateway.refund.side_effect = [GatewayTransientError()] * 4
            # Expect the cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)
            # Check exactly four attempts were made.
            self.assertEqual(gateway.refund.call_count, 4)

        # Scenario: a permanent refusal is rejected and the refund is recorded as failed.
        with self.subTest("permanent refusal"):
            # Build a fresh manager.
            manager, gateway = make_manager()
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Refuse the refund permanently.
            gateway.refund.side_effect = GatewayPermanentError()
            # Expect the cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)
            # Check the refund status records the failure.
            self.assertIs(manager.get_refund_status(booking.booking_id), RefundStatus.FAILED)

        # Scenario: a permanent refusal leaves the booking active.
        with self.subTest("permanent refusal keeps booking active"):
            # Build a fresh manager.
            manager, gateway = make_manager()
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Refuse the refund permanently.
            gateway.refund.side_effect = GatewayPermanentError()
            # Expect the cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)
            # Check the booking is still active.
            self.assertIs(manager.get_booking(booking.booking_id).status, BookingStatus.ACTIVE)

        # Scenario: an unavailable gateway rejects the cancellation and leaves the booking untouched.
        with self.subTest("gateway unavailable"):
            # Build a fresh manager.
            manager, gateway = make_manager()
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Make the gateway unreachable.
            gateway.refund.side_effect = GatewayUnavailableError()
            # Expect the cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)
            # Check the booking is still active.
            self.assertIs(manager.get_booking(booking.booking_id).status, BookingStatus.ACTIVE)

        # Scenario: a booking that is already cancelled is rejected without another refund.
        with self.subTest("already cancelled"):
            # Build a fresh manager.
            manager, gateway = make_manager()
            # Hold a seat and cancel it once.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Perform the first cancellation.
            manager.cancel_booking(booking.booking_id)
            # Expect the second cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to cancel again.
                manager.cancel_booking(booking.booking_id)

        # Scenario: an unknown booking id is rejected.
        with self.subTest("unknown booking"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Expect the cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to cancel an id that was never issued.
                manager.cancel_booking(999)

        # Scenario: a cancellation less than two hours before the start is rejected without a refund.
        with self.subTest("inside cut-off"):
            # Build a manager whose clock is one hour before the start.
            manager, gateway = make_manager(now=START - timedelta(hours=1))
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Expect the cancellation to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation.
                manager.cancel_booking(booking.booking_id)
            # Check no refund was requested.
            gateway.refund.assert_not_called()

        # Scenario: a cancellation exactly two hours before the start is still allowed.
        with self.subTest("exactly at cut-off"):
            # Build a manager whose clock is exactly two hours before the start.
            manager, gateway = make_manager(now=START - timedelta(hours=2))
            # Hold a seat to cancel.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Cancel the booking.
            manager.cancel_booking(booking.booking_id)
            # Check the refund was requested.
            gateway.refund.assert_called_once_with(booking.booking_id, PRICE)

    # Verifies the refund status of a booking, and that unknown ids are rejected.
    def test_get_refund_status(self):
        # Scenario: a booking that was never refunded reports not requested.
        with self.subTest("not requested"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Hold a seat without cancelling it.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Read its refund status.
            status = manager.get_refund_status(booking.booking_id)
            # Check no refund was requested.
            self.assertIs(status, RefundStatus.NOT_REQUESTED)

        # Scenario: a completed cancellation reports refunded.
        with self.subTest("refunded"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Hold a seat and cancel it.
            booking = manager.book_seat("client-1", "s1", 1, 1)
            # Perform the cancellation.
            manager.cancel_booking(booking.booking_id)
            # Read the refund status.
            status = manager.get_refund_status(booking.booking_id)
            # Check the refund was accepted.
            self.assertIs(status, RefundStatus.REFUNDED)

        # Scenario: an unknown booking id is rejected.
        with self.subTest("unknown booking"):
            # Build a fresh manager.
            manager, _ = make_manager()
            # Expect the lookup to be rejected.
            with self.assertRaises(ProcessingException):
                # Look up an id that was never issued.
                manager.get_refund_status(999)
