# Provides the test framework.
import unittest
# Provides timezone-aware times for screenings and the fake clock.
from datetime import datetime, timedelta, timezone
# Provides exact prices.
from decimal import Decimal

# Imports the code under test.
from seat_booking import (
    BookingAlreadyCancelledError,
    CancellationDeadlinePassedError,
    GatewayUnavailableError,
    InvalidSeatError,
    PermanentGatewayError,
    RefundFailedError,
    RefundStatus,
    RefundUnavailableError,
    Room,
    Screening,
    SeatAlreadyBookedError,
    SeatBookingManager,
    TransientGatewayError,
    UnknownBookingError,
    UnknownScreeningError,
)

# Fixed "now" used by the fake clock.
NOW = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
# Ticket price used in the tests.
PRICE = Decimal("9.50")


# Gateway fake that replays a scripted list of outcomes and records every call.
class ScriptedGateway:
    # Stores the outcomes: None means success, an exception instance is raised.
    def __init__(self, *outcomes):
        # Remaining scripted outcomes.
        self.outcomes = list(outcomes)
        # Calls received, as (booking_id, amount).
        self.calls = []

    # Records the call and plays the next outcome (success once the script is exhausted).
    def refund(self, booking_id, amount):
        # Records the call.
        self.calls.append((booking_id, amount))
        # Picks the next outcome.
        outcome = self.outcomes.pop(0) if self.outcomes else None
        # Raises scripted failures.
        if outcome is not None:
            # Plays the failure.
            raise outcome


# End-to-end behaviour of SeatBookingManager with a fake gateway and a fixed clock.
class SeatBookingManagerTest(unittest.TestCase):
    # Builds a manager with one screening starting `starts_in` from NOW.
    def make_manager(self, gateway=None, starts_in=timedelta(days=1)):
        # Uses a succeeding gateway by default.
        self.gateway = gateway if gateway is not None else ScriptedGateway()
        # Builds the manager with a fixed clock.
        manager = SeatBookingManager(self.gateway, clock=lambda: NOW)
        # Registers a 5x10 room screening.
        manager.add_screening(Screening("S1", NOW + starts_in, Room("Room 1", 5, 10), PRICE))
        # Returns the manager.
        return manager

    def test_book_seat_returns_active_booking_at_screening_price(self):
        manager = self.make_manager()
        booking = manager.book_seat("S1", "alice", 2, 3)
        self.assertEqual((booking.screening_id, booking.client_id, booking.row, booking.seat), ("S1", "alice", 2, 3))
        self.assertEqual(booking.price, PRICE)
        self.assertFalse(booking.cancelled)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_booking_an_already_booked_seat_is_rejected(self):
        manager = self.make_manager()
        manager.book_seat("S1", "alice", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("S1", "bob", 2, 3)

    def test_different_seats_can_be_booked(self):
        manager = self.make_manager()
        first = manager.book_seat("S1", "alice", 2, 3)
        second = manager.book_seat("S1", "bob", 2, 4)
        self.assertNotEqual(first.booking_id, second.booking_id)

    def test_booking_unknown_screening_is_rejected(self):
        manager = self.make_manager()
        with self.assertRaises(UnknownScreeningError):
            manager.book_seat("nope", "alice", 1, 1)

    def test_booking_seat_outside_room_is_rejected(self):
        manager = self.make_manager()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(InvalidSeatError):
                manager.book_seat("S1", "alice", row, seat)

    def test_naive_start_time_is_rejected(self):
        manager = SeatBookingManager(ScriptedGateway())
        with self.assertRaises(ValueError):
            manager.add_screening(Screening("S2", datetime(2026, 12, 1, 20, 0), Room("R", 1, 1), PRICE))

    def test_cancel_refunds_price_and_frees_seat(self):
        manager = self.make_manager()
        booking = manager.book_seat("S1", "alice", 2, 3)
        cancelled = manager.cancel_booking(booking.booking_id)
        self.assertTrue(cancelled.cancelled)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.booking_id, PRICE)])
        # The freed seat can be booked again.
        rebooked = manager.book_seat("S1", "bob", 2, 3)
        self.assertEqual(rebooked.client_id, "bob")

    def test_cancel_exactly_two_hours_before_is_allowed(self):
        manager = self.make_manager(starts_in=timedelta(hours=2))
        booking = manager.book_seat("S1", "alice", 1, 1)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_cancel_less_than_two_hours_before_is_rejected(self):
        manager = self.make_manager(starts_in=timedelta(hours=2) - timedelta(seconds=1))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertRaises(CancellationDeadlinePassedError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(self.gateway.calls, [])
        self.assertFalse(booking.cancelled)

    def test_cancel_already_cancelled_booking_is_rejected(self):
        manager = self.make_manager()
        booking = manager.book_seat("S1", "alice", 1, 1)
        manager.cancel_booking(booking.booking_id)
        with self.assertRaises(BookingAlreadyCancelledError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_cancel_unknown_booking_is_rejected(self):
        manager = self.make_manager()
        with self.assertRaises(UnknownBookingError):
            manager.cancel_booking("nope")

    def test_refund_status_of_unknown_booking_is_rejected(self):
        manager = self.make_manager()
        with self.assertRaises(UnknownBookingError):
            manager.get_refund_status("nope")

    def test_transient_failures_are_retried_until_success(self):
        manager = self.make_manager(ScriptedGateway(*[TransientGatewayError()] * 3))
        booking = manager.book_seat("S1", "alice", 1, 1)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertTrue(booking.cancelled)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_transient_failures_beyond_three_retries_fail_and_keep_booking_active(self):
        manager = self.make_manager(ScriptedGateway(*[TransientGatewayError()] * 4))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(RefundFailedError) as raised:
            manager.cancel_booking(booking.booking_id)
        self.assertIsInstance(raised.exception.__cause__, TransientGatewayError)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertFalse(booking.cancelled)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.FAILED)
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("S1", "bob", 1, 1)

    def test_permanent_failure_is_not_retried_and_keeps_booking_active(self):
        manager = self.make_manager(ScriptedGateway(PermanentGatewayError()))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking", "ERROR"), self.assertRaises(RefundFailedError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertFalse(booking.cancelled)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.FAILED)

    def test_booking_can_be_cancelled_again_after_failed_refund(self):
        manager = self.make_manager(ScriptedGateway(PermanentGatewayError()))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking"), self.assertRaises(RefundFailedError):
            manager.cancel_booking(booking.booking_id)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_unavailable_gateway_rejects_cancellation_without_changing_booking(self):
        manager = self.make_manager(ScriptedGateway(GatewayUnavailableError()))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(RefundUnavailableError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertFalse(booking.cancelled)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_default_clock_is_timezone_aware(self):
        manager = SeatBookingManager(ScriptedGateway())
        manager.add_screening(Screening("S1", datetime.now(timezone.utc) + timedelta(days=1), Room("R", 1, 1), PRICE))
        booking = manager.book_seat("S1", "alice", 1, 1)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)


# Allows running the file directly.
if __name__ == "__main__":
    # Runs the tests.
    unittest.main()
