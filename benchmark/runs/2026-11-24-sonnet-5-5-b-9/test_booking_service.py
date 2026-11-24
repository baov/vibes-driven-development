# Unit tests for seat_booking.BookingService, with a scripted fake gateway.
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from seat_booking import (
    BookingService, BookingStatus, GatewayUnavailableError, PermanentGatewayError,
    ProcessingException, RefundStatus, Room, Screening, TransientGatewayError,
)

START = datetime(2026, 12, 1, 20, 0)


# Gateway double: each call pops the next outcome (an exception is raised, None succeeds).
class FakeGateway:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount):
        self.calls.append((booking_id, amount))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.now = START - timedelta(days=1)
        self.screening = Screening("s1", START, Room(rows=5, seats_per_row=10), Decimal("12.50"))

    def make(self, outcomes=()):
        self.gateway = FakeGateway(outcomes)
        return BookingService(self.gateway, clock=lambda: self.now)

    def assertRejected(self, reason, func, *args):
        with self.assertRaises(ProcessingException) as ctx:
            with self.assertLogs("seat_booking", level="ERROR"):
                func(*args)
        self.assertEqual(ctx.exception.reason, reason)

    # --- booking ---
    def test_book_seat_creates_active_booking(self):
        service = self.make()
        booking = service.book_seat("alice", self.screening, 2, 3)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.id), RefundStatus.NONE)

    def test_book_same_seat_twice_is_rejected(self):
        service = self.make()
        service.book_seat("alice", self.screening, 2, 3)
        self.assertRejected("SEAT_ALREADY_BOOKED", service.book_seat, "bob", self.screening, 2, 3)

    def test_same_seat_other_screening_is_allowed(self):
        service = self.make()
        service.book_seat("alice", self.screening, 2, 3)
        other = Screening("s2", START, self.screening.room, Decimal("9"))
        self.assertEqual(service.book_seat("bob", other, 2, 3).client_id, "bob")

    def test_seat_outside_room_is_rejected(self):
        service = self.make()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            self.assertRejected("INVALID_SEAT", service.book_seat, "a", self.screening, row, seat)

    def test_booking_after_start_is_rejected(self):
        service = self.make()
        self.now = START
        self.assertRejected("SCREENING_STARTED", service.book_seat, "a", self.screening, 1, 1)

    def test_unexpected_error_is_wrapped(self):
        service = self.make()
        self.assertRejected("INTERNAL", service.book_seat, "a", None, 1, 1)

    # --- cancellation ---
    def test_cancel_refunds_and_frees_seat(self):
        service = self.make()
        booking = service.book_seat("alice", self.screening, 2, 3)
        service.cancel_booking(booking.id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(service.get_refund_status(booking.id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.id, Decimal("12.50"))])
        self.assertEqual(service.book_seat("bob", self.screening, 2, 3).client_id, "bob")

    def test_cancel_exactly_two_hours_before_is_allowed(self):
        service = self.make()
        booking = service.book_seat("a", self.screening, 1, 1)
        self.now = START - timedelta(hours=2)
        service.cancel_booking(booking.id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_cancel_less_than_two_hours_before_is_rejected(self):
        service = self.make()
        booking = service.book_seat("a", self.screening, 1, 1)
        self.now = START - timedelta(hours=2) + timedelta(seconds=1)
        self.assertRejected("TOO_LATE_TO_CANCEL", service.cancel_booking, booking.id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_cancel_unknown_booking_is_rejected(self):
        self.assertRejected("UNKNOWN_BOOKING", self.make().cancel_booking, 99)

    def test_cancel_twice_is_rejected_without_second_refund(self):
        service = self.make()
        booking = service.book_seat("a", self.screening, 1, 1)
        service.cancel_booking(booking.id)
        self.assertRejected("ALREADY_CANCELLED", service.cancel_booking, booking.id)
        self.assertEqual(len(self.gateway.calls), 1)

    # --- refund failures ---
    def test_transient_failures_are_retried_then_succeed(self):
        service = self.make([TransientGatewayError(), TransientGatewayError(), TransientGatewayError()])
        booking = service.book_seat("a", self.screening, 1, 1)
        service.cancel_booking(booking.id)
        self.assertEqual(len(self.gateway.calls), 4)  # first attempt + 3 retries
        self.assertEqual(service.get_refund_status(booking.id), RefundStatus.REFUNDED)

    def test_transient_failures_beyond_retries_keep_booking_active(self):
        service = self.make([TransientGatewayError()] * 4)
        booking = service.book_seat("a", self.screening, 1, 1)
        self.assertRejected("REFUND_FAILED", service.cancel_booking, booking.id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.id), RefundStatus.FAILED)

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        service = self.make([PermanentGatewayError()])
        booking = service.book_seat("a", self.screening, 1, 1)
        self.assertRejected("REFUND_FAILED", service.cancel_booking, booking.id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.id), RefundStatus.FAILED)

    def test_unavailable_gateway_rejects_cancellation(self):
        service = self.make([GatewayUnavailableError()])
        booking = service.book_seat("a", self.screening, 1, 1)
        self.assertRejected("GATEWAY_UNAVAILABLE", service.cancel_booking, booking.id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.id), RefundStatus.NONE)
        # Cancellation can be retried once the gateway is back.
        service.cancel_booking(booking.id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_unexpected_gateway_error_is_wrapped(self):
        service = self.make([RuntimeError("boom")])
        booking = service.book_seat("a", self.screening, 1, 1)
        self.assertRejected("INTERNAL", service.cancel_booking, booking.id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)

    # --- refund status ---
    def test_refund_status_of_unknown_booking_is_rejected(self):
        self.assertRejected("UNKNOWN_BOOKING", self.make().get_refund_status, 42)


if __name__ == "__main__":
    unittest.main()
