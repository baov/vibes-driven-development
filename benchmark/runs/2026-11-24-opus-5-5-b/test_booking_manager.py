import logging
import unittest
from datetime import datetime, timedelta

from seat_booking import (
    BOOKING_ACTIVE,
    BOOKING_CANCELLED,
    REFUND_FAILED,
    REFUND_NOT_REQUESTED,
    REFUND_SUCCEEDED,
    BookingManager,
    BookingNotCancellableException,
    GatewayUnavailableError,
    PermanentGatewayError,
    RefundFailedException,
    RefundUnavailableException,
    Screening,
    SeatUnavailableException,
    TransientGatewayError,
    UnknownBookingException,
    UnknownScreeningException,
)

NOW = datetime(2026, 11, 24, 18, 0)


class ScriptedGateway:
    """Fake payment gateway: raises the scripted errors in order, then succeeds."""

    def __init__(self, *failures):
        # Errors to raise on successive calls.
        self.failures = list(failures)
        # Every (booking_id, amount) the gateway was called with.
        self.calls = []

    def refund(self, booking_id, amount):
        # Record the call.
        self.calls.append((booking_id, amount))
        # Raise the next scripted failure, if any.
        if self.failures:
            raise self.failures.pop(0)


class BookingManagerTest(unittest.TestCase):
    def setUp(self):
        # Silence the expected warning/error logs during tests.
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.gateway = ScriptedGateway()
        self.now = NOW
        self.manager = BookingManager(self.gateway, clock=lambda: self.now)
        self.manager.add_screening(
            Screening("s1", starts_at=NOW + timedelta(hours=5), rows=10, seats_per_row=12, price="12.50")
        )

    # --- booking -----------------------------------------------------------

    def test_book_free_seat_creates_active_booking(self):
        booking = self.manager.book_seat("s1", "alice", 3, 7)
        self.assertEqual(booking.status, BOOKING_ACTIVE)
        self.assertEqual((booking.screening_id, booking.client_id, booking.row, booking.seat), ("s1", "alice", 3, 7))
        self.assertEqual(booking.price, "12.50")
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_NOT_REQUESTED)

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.manager.book_seat("s1", "alice", 3, 7)
        with self.assertRaises(SeatUnavailableException):
            self.manager.book_seat("s1", "bob", 3, 7)

    def test_same_seat_in_another_screening_can_be_booked(self):
        self.manager.add_screening(Screening("s2", NOW + timedelta(hours=5), 10, 12, "9.00"))
        self.manager.book_seat("s1", "alice", 3, 7)
        booking = self.manager.book_seat("s2", "bob", 3, 7)
        self.assertEqual(booking.status, BOOKING_ACTIVE)

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        for row, seat in [(0, 1), (11, 1), (1, 0), (1, 13)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(SeatUnavailableException):
                self.manager.book_seat("s1", "alice", row, seat)

    def test_booking_for_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningException):
            self.manager.book_seat("nope", "alice", 1, 1)

    # --- cancellation ------------------------------------------------------

    def test_cancel_refunds_full_price_and_frees_the_seat(self):
        booking = self.manager.book_seat("s1", "alice", 3, 7)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BOOKING_CANCELLED)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_SUCCEEDED)
        self.assertEqual(self.gateway.calls, [(booking.booking_id, "12.50")])
        # The seat can be booked again.
        self.assertEqual(self.manager.book_seat("s1", "bob", 3, 7).status, BOOKING_ACTIVE)

    def test_cancel_exactly_two_hours_before_start_is_allowed(self):
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        self.now = NOW + timedelta(hours=3)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BOOKING_CANCELLED)

    def test_cancel_less_than_two_hours_before_start_is_rejected(self):
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        self.now = NOW + timedelta(hours=3, seconds=1)
        with self.assertRaises(BookingNotCancellableException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BOOKING_ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_cancel_already_cancelled_booking_is_rejected(self):
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        self.manager.cancel_booking(booking.booking_id)
        with self.assertRaises(BookingNotCancellableException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_cancel_unknown_booking_is_rejected(self):
        with self.assertRaises(UnknownBookingException):
            self.manager.cancel_booking("nope")

    def test_cancel_while_refund_in_flight_is_rejected(self):
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        nested_errors = []

        def reentrant_refund(booking_id, amount):
            try:
                self.manager.cancel_booking(booking_id)
            except BookingNotCancellableException as exc:
                nested_errors.append(exc)

        self.gateway.refund = reentrant_refund
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(nested_errors), 1)
        self.assertEqual(booking.status, BOOKING_CANCELLED)

    # --- gateway failures --------------------------------------------------

    def test_transient_failures_are_retried_until_success(self):
        self.gateway.failures = [TransientGatewayError()] * 3
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BOOKING_CANCELLED)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_SUCCEEDED)

    def test_transient_failures_beyond_three_retries_fail_the_refund(self):
        self.gateway.failures = [TransientGatewayError()] * 4
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundFailedException) as ctx:
            self.manager.cancel_booking(booking.booking_id)
        self.assertIsInstance(ctx.exception.__cause__, TransientGatewayError)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BOOKING_ACTIVE)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_FAILED)

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        self.gateway.failures = [PermanentGatewayError()]
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundFailedException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BOOKING_ACTIVE)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_FAILED)
        # The seat is still held.
        with self.assertRaises(SeatUnavailableException):
            self.manager.book_seat("s1", "bob", 1, 1)

    def test_failed_refund_can_be_retried_by_cancelling_again(self):
        self.gateway.failures = [PermanentGatewayError()]
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundFailedException):
            self.manager.cancel_booking(booking.booking_id)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BOOKING_CANCELLED)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_SUCCEEDED)

    def test_unavailable_gateway_rejects_cancellation_and_leaves_status_unchanged(self):
        self.gateway.failures = [GatewayUnavailableError()]
        booking = self.manager.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundUnavailableException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BOOKING_ACTIVE)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), REFUND_NOT_REQUESTED)
        # Cancelling again once the gateway is back works.
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BOOKING_CANCELLED)

    def test_refund_status_of_unknown_booking_is_rejected(self):
        with self.assertRaises(UnknownBookingException):
            self.manager.get_refund_status("nope")


if __name__ == "__main__":
    unittest.main()
