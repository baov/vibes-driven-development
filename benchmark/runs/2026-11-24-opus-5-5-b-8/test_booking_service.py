import logging
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from seat_booking.booking_service import (
    BookingAlreadyCancelledError,
    BookingService,
    BookingStatus,
    CancellationDeadlinePassedError,
    GatewayUnavailableError,
    InvalidSeatError,
    PermanentGatewayError,
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

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
PRICE = Decimal("9.50")


class ScriptedGateway:
    """Fake gateway: each refund call consumes the next scripted outcome (an exception or None)."""

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
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.now = NOW

    def make_service(self, gateway=None, starts_in=timedelta(hours=5)):
        self.gateway = gateway or ScriptedGateway()
        service = BookingService(self.gateway, clock=lambda: self.now)
        service.add_screening(Screening("S1", NOW + starts_in, Room("Room 1", rows=5, seats_per_row=10), PRICE))
        return service

    # --- booking -----------------------------------------------------------

    def test_book_free_seat(self):
        service = self.make_service()
        booking = service.book("S1", "alice", 2, 3)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual((booking.screening_id, booking.client_id, booking.row, booking.seat), ("S1", "alice", 2, 3))
        self.assertEqual(booking.amount, PRICE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = self.make_service()
        service.book("S1", "alice", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("S1", "bob", 2, 3)

    def test_same_seat_in_another_screening_is_independent(self):
        service = self.make_service()
        service.add_screening(Screening("S2", NOW + timedelta(days=1), Room("Room 1", 5, 10), PRICE))
        service.book("S1", "alice", 2, 3)
        self.assertEqual(service.book("S2", "bob", 2, 3).screening_id, "S2")

    def test_booking_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.make_service().book("nope", "alice", 1, 1)

    def test_booking_seat_outside_room_is_rejected(self):
        service = self.make_service()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(InvalidSeatError):
                service.book("S1", "alice", row, seat)
        self.assertEqual(service.book("S1", "alice", 5, 10).row, 5)

    # --- cancellation ------------------------------------------------------

    def test_cancel_refunds_and_frees_the_seat(self):
        service = self.make_service()
        booking = service.book("S1", "alice", 2, 3)
        cancelled = service.cancel(booking.booking_id)
        self.assertEqual(cancelled.status, BookingStatus.CANCELLED)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.booking_id, PRICE)])
        self.assertEqual(service.book("S1", "bob", 2, 3).client_id, "bob")

    def test_cancel_exactly_two_hours_before_is_allowed(self):
        service = self.make_service(starts_in=timedelta(hours=2))
        booking = service.book("S1", "alice", 1, 1)
        self.assertEqual(service.cancel(booking.booking_id).status, BookingStatus.CANCELLED)

    def test_cancel_less_than_two_hours_before_is_rejected(self):
        service = self.make_service(starts_in=timedelta(hours=2))
        booking = service.book("S1", "alice", 1, 1)
        self.now = NOW + timedelta(seconds=1)
        with self.assertRaises(CancellationDeadlinePassedError):
            service.cancel(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_cancel_unknown_booking_is_rejected(self):
        with self.assertRaises(UnknownBookingError):
            self.make_service().cancel("nope")

    def test_cancel_already_cancelled_booking_is_rejected(self):
        service = self.make_service()
        booking = service.book("S1", "alice", 1, 1)
        service.cancel(booking.booking_id)
        with self.assertRaises(BookingAlreadyCancelledError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    # --- refund gateway failures --------------------------------------------

    def test_transient_failures_are_retried_until_success(self):
        service = self.make_service(ScriptedGateway(*[TransientGatewayError()] * 3))
        booking = service.book("S1", "alice", 1, 1)
        service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_transient_failures_beyond_three_retries_fail_the_refund(self):
        service = self.make_service(ScriptedGateway(*[TransientGatewayError()] * 4))
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.FAILED)

    def test_permanent_failure_keeps_booking_active(self):
        service = self.make_service(ScriptedGateway(PermanentGatewayError()))
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.FAILED)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("S1", "bob", 1, 1)

    def test_cancel_can_be_retried_after_a_failed_refund(self):
        service = self.make_service(ScriptedGateway(PermanentGatewayError()))
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.booking_id)
        service.cancel(booking.booking_id)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_unavailable_gateway_rejects_cancellation(self):
        service = self.make_service(ScriptedGateway(GatewayUnavailableError()))
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundGatewayUnavailableError):
            service.cancel(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_refund_status_of_unknown_booking_is_rejected(self):
        with self.assertRaises(UnknownBookingError):
            self.make_service().refund_status("nope")


if __name__ == "__main__":
    unittest.main()
