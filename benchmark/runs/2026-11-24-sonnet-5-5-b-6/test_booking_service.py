import unittest
from datetime import datetime, timedelta

from seat_booking import (
    BookingAlreadyCancelledError, BookingService, BookingStatus,
    CancellationTooLateError, GatewayPermanentError, GatewayTransientError,
    GatewayUnavailableError, InvalidSeatError, RefundFailedError, RefundStatus,
    RefundUnavailableError, Room, Screening, SeatAlreadyBookedError,
    UnknownBookingError, UnknownScreeningError,
)

START = datetime(2026, 12, 1, 20, 0)


class FakeGateway:
    """Plays a script of outcomes (exceptions are raised, None succeeds)."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount_cents):
        self.calls.append((booking_id, amount_cents))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome:
            raise outcome


class BookingServiceTest(unittest.TestCase):
    def make(self, gateway=None, now=START - timedelta(hours=5)):
        self.gateway = gateway or FakeGateway()
        self.now = now
        service = BookingService(self.gateway, clock=lambda: self.now)
        service.add_screening(Screening("s1", START, Room(5, 10), 1250))
        return service

    def test_book_returns_active_booking_at_screening_price(self):
        booking = self.make().book("s1", "ann", 2, 3)
        self.assertEqual((booking.status, booking.amount_cents),
                         (BookingStatus.ACTIVE, 1250))

    def test_double_booking_rejected(self):
        service = self.make()
        service.book("s1", "ann", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", "bob", 2, 3)

    def test_invalid_seat_and_screening_rejected(self):
        service = self.make()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.assertRaises(InvalidSeatError):
                service.book("s1", "ann", row, seat)
        with self.assertRaises(UnknownScreeningError):
            service.book("nope", "ann", 1, 1)

    def test_cancel_refunds_and_frees_seat(self):
        service = self.make()
        booking = service.book("s1", "ann", 1, 1)
        service.cancel(booking.id)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.REFUNDED)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(self.gateway.calls, [(booking.id, 1250)])
        service.book("s1", "bob", 1, 1)  # seat is free again

    def test_cancel_allowed_exactly_two_hours_before_but_not_after(self):
        service = self.make(now=START - timedelta(hours=2))
        service.cancel(service.book("s1", "ann", 1, 1).id)
        booking = service.book("s1", "ann", 1, 2)
        self.now = START - timedelta(hours=2) + timedelta(seconds=1)
        with self.assertRaises(CancellationTooLateError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1)  # no refund attempted

    def test_cancel_twice_or_unknown_rejected(self):
        service = self.make()
        booking = service.book("s1", "ann", 1, 1)
        service.cancel(booking.id)
        with self.assertRaises(BookingAlreadyCancelledError):
            service.cancel(booking.id)
        with self.assertRaises(UnknownBookingError):
            service.cancel(999)
        with self.assertRaises(UnknownBookingError):
            service.refund_status(999)

    def test_transient_failures_are_retried_up_to_three_times(self):
        service = self.make(FakeGateway(*[GatewayTransientError()] * 3))
        booking = service.book("s1", "ann", 1, 1)
        service.cancel(booking.id)  # 3 failures then success
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_transient_failures_exhausted_keep_booking_active(self):
        service = self.make(FakeGateway(*[GatewayTransientError()] * 4))
        booking = service.book("s1", "ann", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual((booking.status, service.refund_status(booking.id)),
                         (BookingStatus.ACTIVE, RefundStatus.FAILED))

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        service = self.make(FakeGateway(GatewayPermanentError()))
        booking = service.book("s1", "ann", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual((booking.status, service.refund_status(booking.id)),
                         (BookingStatus.ACTIVE, RefundStatus.FAILED))
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", "bob", 1, 1)

    def test_unavailable_gateway_rejects_cancellation_and_can_be_retried_later(self):
        service = self.make(FakeGateway(GatewayUnavailableError()))
        booking = service.book("s1", "ann", 1, 1)
        with self.assertRaises(RefundUnavailableError):
            service.cancel(booking.id)
        self.assertEqual((booking.status, service.refund_status(booking.id)),
                         (BookingStatus.ACTIVE, RefundStatus.NONE))
        service.cancel(booking.id)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.REFUNDED)


if __name__ == "__main__":
    unittest.main()
