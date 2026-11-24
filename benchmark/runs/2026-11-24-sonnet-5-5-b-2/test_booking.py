import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from seat_booking import (
    AlreadyCancelledError, BookingService, BookingStatus, CancellationTooLateError,
    GatewayUnavailableError, InvalidSeatError, PermanentGatewayError, RefundFailedError,
    RefundStatus, RefundUnavailableError, Room, Screening, ScreeningStartedError,
    SeatAlreadyBookedError, TransientGatewayError, UnknownBookingError,
)

START = datetime(2026, 12, 1, 20, 0)


class FakeGateway:
    """Plays back scripted outcomes: an exception to raise, or None for success."""

    def __init__(self, *outcomes):
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
        self.screening = Screening(1, START, Room(5, 10), "12.50")

    def service(self, *outcomes):
        self.gateway = FakeGateway(*outcomes)
        return BookingService(self.gateway, clock=lambda: self.now)

    def test_book_then_double_book_rejected(self):
        service = self.service()
        booking = service.book("alice", self.screening, 2, 3)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("bob", self.screening, 2, 3)
        service.book("bob", self.screening, 2, 4)

    def test_same_seat_other_screening_ok(self):
        service = self.service()
        service.book("alice", self.screening, 1, 1)
        service.book("bob", Screening(2, START, Room(5, 10), 10), 1, 1)

    def test_invalid_seat_and_started_screening(self):
        service = self.service()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.assertRaises(InvalidSeatError):
                service.book("a", self.screening, row, seat)
        self.now = START
        with self.assertRaises(ScreeningStartedError):
            service.book("a", self.screening, 1, 1)

    def test_cancel_refunds_and_frees_seat(self):
        service = self.service()
        booking = service.book("alice", self.screening, 1, 1)
        self.assertEqual(service.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)
        service.cancel(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(service.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.booking_id, Decimal("12.50"))])
        service.book("bob", self.screening, 1, 1)

    def test_cancel_deadline_boundary(self):
        service = self.service()
        booking = service.book("alice", self.screening, 1, 1)
        self.now = START - timedelta(hours=2, seconds=-1)
        with self.assertRaises(CancellationTooLateError):
            service.cancel(booking.booking_id)
        self.assertEqual(self.gateway.calls, [])
        self.now = START - timedelta(hours=2)
        service.cancel(booking.booking_id)

    def test_cancel_unknown_and_twice(self):
        service = self.service()
        with self.assertRaises(UnknownBookingError):
            service.cancel(99)
        with self.assertRaises(UnknownBookingError):
            service.get_refund_status(99)
        booking = service.book("alice", self.screening, 1, 1)
        service.cancel(booking.booking_id)
        with self.assertRaises(AlreadyCancelledError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_transient_failures_are_retried_up_to_three_times(self):
        service = self.service(TransientGatewayError(), TransientGatewayError(), TransientGatewayError())
        booking = service.book("alice", self.screening, 1, 1)
        service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.refund_status, RefundStatus.REFUNDED)

    def test_transient_failures_exhausted_keep_booking_active(self):
        service = self.service(*[TransientGatewayError()] * 10)
        booking = service.book("alice", self.screening, 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.booking_id), RefundStatus.FAILED)

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        service = self.service(PermanentGatewayError())
        booking = service.book("alice", self.screening, 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.booking_id), RefundStatus.FAILED)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("bob", self.screening, 1, 1)
        service.cancel(booking.booking_id)  # a later cancellation can still succeed
        self.assertEqual(booking.refund_status, RefundStatus.REFUNDED)

    def test_gateway_unavailable_rejects_cancellation(self):
        service = self.service(GatewayUnavailableError())
        booking = service.book("alice", self.screening, 1, 1)
        with self.assertRaises(RefundUnavailableError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)


if __name__ == "__main__":
    unittest.main()
