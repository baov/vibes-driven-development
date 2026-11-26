import logging
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from seat_booking import (
    BookingAlreadyCancelledError,
    BookingManager,
    BookingNotFoundError,
    CancellationWindowClosedError,
    GatewayPermanentError,
    GatewayTransientError,
    GatewayUnavailableError,
    InvalidSeatError,
    ProcessingException,
    RefundFailedError,
    RefundStatus,
    RefundUnavailableError,
    Room,
    Screening,
    ScreeningNotFoundError,
    SeatAlreadyBookedError,
)

# Fixed "now" used by every test.
NOW = datetime(2026, 11, 24, 18, 0)


# Gateway double that replays a script of outcomes: None means success, an exception instance is raised.
class ScriptedGateway:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount):
        self.calls.append((booking_id, amount))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome


class BookingManagerTest(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.room = Room(name="Room 1", rows=5, seats_per_row=10)

    def make_manager(self, gateway, starts_in=timedelta(hours=5)):
        manager = BookingManager(gateway, clock=lambda: NOW)
        manager.add_screening(Screening("S1", NOW + starts_in, self.room, Decimal("12.50")))
        return manager

    # --- booking ---

    def test_book_seat_returns_active_booking_at_screening_price(self):
        manager = self.make_manager(ScriptedGateway())
        booking = manager.book_seat("alice", "S1", 2, 3)
        self.assertEqual(("S1", "alice", 2, 3), (booking.screening_id, booking.client_id, booking.row, booking.seat))
        self.assertEqual(Decimal("12.50"), booking.price)
        self.assertTrue(booking.active)
        self.assertEqual(RefundStatus.NOT_REQUESTED, manager.get_refund_status(booking.booking_id))

    def test_booking_an_already_booked_seat_is_rejected(self):
        manager = self.make_manager(ScriptedGateway())
        manager.book_seat("alice", "S1", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("bob", "S1", 2, 3)

    def test_same_seat_can_be_booked_for_different_screenings(self):
        manager = self.make_manager(ScriptedGateway())
        manager.add_screening(Screening("S2", NOW + timedelta(days=1), self.room, Decimal("10")))
        first = manager.book_seat("alice", "S1", 1, 1)
        second = manager.book_seat("bob", "S2", 1, 1)
        self.assertNotEqual(first.booking_id, second.booking_id)

    def test_booking_unknown_screening_is_rejected(self):
        manager = self.make_manager(ScriptedGateway())
        with self.assertRaises(ScreeningNotFoundError):
            manager.book_seat("alice", "nope", 1, 1)

    def test_booking_seat_outside_room_is_rejected(self):
        manager = self.make_manager(ScriptedGateway())
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(InvalidSeatError):
                manager.book_seat("alice", "S1", row, seat)
        # Corners of the grid are valid.
        manager.book_seat("alice", "S1", 1, 1)
        manager.book_seat("alice", "S1", 5, 10)

    # --- cancellation window ---

    def test_cancel_refunds_price_frees_seat_and_marks_refunded(self):
        gateway = ScriptedGateway(None)
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 2, 3)
        cancelled = manager.cancel_booking(booking.booking_id)
        self.assertFalse(cancelled.active)
        self.assertEqual([(booking.booking_id, Decimal("12.50"))], gateway.calls)
        self.assertEqual(RefundStatus.REFUNDED, manager.get_refund_status(booking.booking_id))
        manager.book_seat("bob", "S1", 2, 3)  # seat is free again

    def test_cancel_exactly_two_hours_before_start_is_allowed(self):
        manager = self.make_manager(ScriptedGateway(None), starts_in=timedelta(hours=2))
        booking = manager.book_seat("alice", "S1", 1, 1)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(RefundStatus.REFUNDED, manager.get_refund_status(booking.booking_id))

    def test_cancel_less_than_two_hours_before_start_is_rejected(self):
        gateway = ScriptedGateway()
        manager = self.make_manager(gateway, starts_in=timedelta(hours=2) - timedelta(seconds=1))
        booking = manager.book_seat("alice", "S1", 1, 1)
        with self.assertRaises(CancellationWindowClosedError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual([], gateway.calls)
        self.assertTrue(booking.active)

    # --- invalid cancellations ---

    def test_cancel_unknown_booking_is_rejected(self):
        manager = self.make_manager(ScriptedGateway())
        with self.assertRaises(BookingNotFoundError):
            manager.cancel_booking("B999")

    def test_cancel_already_cancelled_booking_is_rejected_without_second_refund(self):
        gateway = ScriptedGateway(None)
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        manager.cancel_booking(booking.booking_id)
        with self.assertRaises(BookingAlreadyCancelledError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(1, len(gateway.calls))

    # --- gateway failures ---

    def test_transient_failures_are_retried_until_success(self):
        gateway = ScriptedGateway(GatewayTransientError(), GatewayTransientError(), GatewayTransientError(), None)
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(4, len(gateway.calls))  # 1 attempt + 3 retries
        self.assertEqual(RefundStatus.REFUNDED, manager.get_refund_status(booking.booking_id))

    def test_transient_failures_beyond_three_retries_fail_and_keep_booking_active(self):
        gateway = ScriptedGateway(*[GatewayTransientError() for _ in range(5)])
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        with self.assertRaises(RefundFailedError) as ctx:
            manager.cancel_booking(booking.booking_id)
        self.assertIsInstance(ctx.exception.__cause__, GatewayTransientError)
        self.assertEqual(4, len(gateway.calls))
        self.assertTrue(booking.active)
        self.assertEqual(RefundStatus.FAILED, manager.get_refund_status(booking.booking_id))
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("bob", "S1", 1, 1)

    def test_permanent_failure_is_not_retried_and_keeps_booking_active(self):
        gateway = ScriptedGateway(GatewayPermanentError("refused"))
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        with self.assertRaises(RefundFailedError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(1, len(gateway.calls))
        self.assertTrue(booking.active)
        self.assertEqual(RefundStatus.FAILED, manager.get_refund_status(booking.booking_id))
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("bob", "S1", 1, 1)

    def test_failed_refund_can_be_retried_by_cancelling_again(self):
        gateway = ScriptedGateway(GatewayPermanentError(), None)
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        with self.assertRaises(RefundFailedError):
            manager.cancel_booking(booking.booking_id)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(RefundStatus.REFUNDED, manager.get_refund_status(booking.booking_id))

    def test_unavailable_gateway_rejects_cancellation_and_changes_nothing(self):
        gateway = ScriptedGateway(GatewayUnavailableError("down"))
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        with self.assertRaises(RefundUnavailableError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(1, len(gateway.calls))
        self.assertTrue(booking.active)
        self.assertEqual(RefundStatus.NOT_REQUESTED, manager.get_refund_status(booking.booking_id))

    def test_unavailable_gateway_during_retries_rejects_cancellation(self):
        gateway = ScriptedGateway(GatewayTransientError(), GatewayUnavailableError())
        manager = self.make_manager(gateway)
        booking = manager.book_seat("alice", "S1", 1, 1)
        with self.assertRaises(RefundUnavailableError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(2, len(gateway.calls))
        self.assertTrue(booking.active)

    # --- refund status ---

    def test_refund_status_of_unknown_booking_is_rejected(self):
        manager = self.make_manager(ScriptedGateway())
        with self.assertRaises(BookingNotFoundError):
            manager.get_refund_status("B999")

    def test_all_package_errors_share_a_common_base(self):
        manager = self.make_manager(ScriptedGateway())
        with self.assertRaises(ProcessingException):
            manager.cancel_booking("B999")


if __name__ == "__main__":
    unittest.main()
