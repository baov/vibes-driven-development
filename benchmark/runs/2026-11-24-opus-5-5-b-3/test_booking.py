import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from seat_booking.booking import (
    BookingAlreadyCancelledError,
    BookingManager,
    BookingStatus,
    CancellationDeadlinePassedError,
    GatewayUnavailableError,
    InvalidSeatError,
    PermanentGatewayError,
    ProcessingException,
    RefundFailedError,
    RefundGatewayUnavailableError,
    RefundStatus,
    Room,
    Screening,
    SeatAlreadyBookedError,
    TransientGatewayError,
    UnknownBookingError,
    UnknownScreeningError,
)

START = datetime(2026, 12, 1, 20, 0)
PRICE = Decimal("12.50")


class FakeGateway:
    """Raises the scripted errors in order, then succeeds. Records every call."""

    def __init__(self, *errors):
        self.errors = list(errors)
        self.calls = []

    def refund(self, booking_id, amount):
        self.calls.append((booking_id, amount))
        if self.errors:
            raise self.errors.pop(0)


class BookingManagerTest(unittest.TestCase):
    def make(self, gateway=None, now=START - timedelta(days=1)):
        self.gateway = gateway or FakeGateway()
        self.now = now
        manager = BookingManager(self.gateway, clock=lambda: self.now)
        manager.add_screening(Screening("S1", START, Room("Room 1", rows=5, seats_per_row=10), PRICE))
        return manager

    # --- booking ---------------------------------------------------------

    def test_book_free_seat(self):
        manager = self.make()
        booking = manager.book_seat("S1", "alice", 2, 3)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(booking.price, PRICE)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)
        self.assertIs(manager.get_booking(booking.booking_id), booking)

    def test_booking_already_booked_seat_is_rejected(self):
        manager = self.make()
        manager.book_seat("S1", "alice", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("S1", "bob", 2, 3)

    def test_same_seat_on_other_screening_is_bookable(self):
        manager = self.make()
        manager.add_screening(Screening("S2", START, Room("Room 1", 5, 10), PRICE))
        manager.book_seat("S1", "alice", 2, 3)
        self.assertEqual(manager.book_seat("S2", "bob", 2, 3).screening_id, "S2")

    def test_seat_outside_room_is_rejected(self):
        manager = self.make()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.assertRaises(InvalidSeatError):
                manager.book_seat("S1", "alice", row, seat)

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.make().book_seat("nope", "alice", 1, 1)

    def test_rejections_are_processing_exceptions(self):
        with self.assertRaises(ProcessingException):
            self.make().book_seat("nope", "alice", 1, 1)

    # --- cancellation ----------------------------------------------------

    def test_cancel_refunds_price_and_frees_seat(self):
        manager = self.make()
        booking = manager.book_seat("S1", "alice", 1, 1)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.booking_id, PRICE)])
        self.assertEqual(manager.book_seat("S1", "bob", 1, 1).client_id, "bob")

    def test_cancel_exactly_two_hours_before_is_allowed(self):
        manager = self.make(now=START - timedelta(hours=2))
        booking = manager.book_seat("S1", "alice", 1, 1)
        self.assertEqual(manager.cancel_booking(booking.booking_id).status, BookingStatus.CANCELLED)

    def test_cancel_less_than_two_hours_before_is_rejected(self):
        manager = self.make()
        booking = manager.book_seat("S1", "alice", 1, 1)
        self.now = START - timedelta(hours=2) + timedelta(seconds=1)
        with self.assertRaises(CancellationDeadlinePassedError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_cancel_twice_is_rejected(self):
        manager = self.make()
        booking = manager.book_seat("S1", "alice", 1, 1)
        manager.cancel_booking(booking.booking_id)
        with self.assertRaises(BookingAlreadyCancelledError):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_cancel_unknown_booking_is_rejected(self):
        with self.assertRaises(UnknownBookingError):
            self.make().cancel_booking("B999")

    # --- gateway failures ------------------------------------------------

    def test_transient_failures_are_retried_up_to_three_times(self):
        manager = self.make(FakeGateway(*[TransientGatewayError("timeout")] * 3))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking.booking", "WARNING"):
            manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_transient_failure_after_three_retries_keeps_booking_active(self):
        manager = self.make(FakeGateway(*[TransientGatewayError("timeout")] * 4))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking.booking", "WARNING"):
            with self.assertRaises(RefundFailedError) as ctx:
                manager.cancel_booking(booking.booking_id)
        self.assertIsInstance(ctx.exception.__cause__, TransientGatewayError)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.FAILED)
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("S1", "bob", 1, 1)

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        manager = self.make(FakeGateway(PermanentGatewayError("card closed")))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking.booking", "ERROR"):
            with self.assertRaises(RefundFailedError) as ctx:
                manager.cancel_booking(booking.booking_id)
        self.assertIsInstance(ctx.exception.__cause__, PermanentGatewayError)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.FAILED)

    def test_failed_refund_can_be_retried_by_cancelling_again(self):
        manager = self.make(FakeGateway(PermanentGatewayError("declined")))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking.booking", "ERROR"), self.assertRaises(RefundFailedError):
            manager.cancel_booking(booking.booking_id)
        manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_unavailable_gateway_rejects_cancellation(self):
        manager = self.make(FakeGateway(GatewayUnavailableError("down")))
        booking = manager.book_seat("S1", "alice", 1, 1)
        with self.assertLogs("seat_booking.booking", "ERROR"):
            with self.assertRaises(RefundGatewayUnavailableError) as ctx:
                manager.cancel_booking(booking.booking_id)
        self.assertIsInstance(ctx.exception.__cause__, GatewayUnavailableError)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(manager.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    # --- refund status ---------------------------------------------------

    def test_refund_status_of_unknown_booking_is_rejected(self):
        with self.assertRaises(UnknownBookingError):
            self.make().get_refund_status("B999")

    def test_get_unknown_booking_returns_none(self):
        self.assertIsNone(self.make().get_booking("B999"))


if __name__ == "__main__":
    unittest.main()
