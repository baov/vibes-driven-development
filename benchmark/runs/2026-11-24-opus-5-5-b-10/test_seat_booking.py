import logging
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from seat_booking import (
    BookingAlreadyCancelledError,
    BookingNotFoundError,
    BookingService,
    BookingStatus,
    CancellationDeadlinePassedError,
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
NOW = datetime(2026, 11, 24, 12, 0)


class FakeGateway:
    """Payment gateway double: raises the queued errors in order, then succeeds."""

    def __init__(self, *errors):
        # Errors to raise, one per call, before succeeding.
        self.errors = list(errors)
        # Every (booking_id, amount) the service asked to refund.
        self.calls = []

    def refund(self, booking_id, amount):
        # Record the call.
        self.calls.append((booking_id, amount))
        # Fail with the next queued error, if any.
        if self.errors:
            raise self.errors.pop(0)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        # Silence the expected warning/error logs.
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def make_service(self, gateway=None, starts_in=timedelta(days=1)):
        # Service with a fixed clock and one 5x10 screening at 9.50.
        self.gateway = gateway or FakeGateway()
        service = BookingService(self.gateway, clock=lambda: NOW)
        service.add_screening(Screening("s1", NOW + starts_in, Room("Room 1", rows=5, seats_per_row=10), Decimal("9.50")))
        return service

    # --- booking ---------------------------------------------------------

    def test_booking_a_free_seat_creates_an_active_booking(self):
        service = self.make_service()
        booking = service.book_seat("s1", "alice", row=2, seat=3)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual((booking.screening_id, booking.client_id, booking.row, booking.seat), ("s1", "alice", 2, 3))
        self.assertEqual(booking.price, Decimal("9.50"))
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = self.make_service()
        service.book_seat("s1", "alice", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book_seat("s1", "bob", 2, 3)

    def test_same_seat_can_be_booked_on_another_screening(self):
        service = self.make_service()
        service.add_screening(Screening("s2", NOW + timedelta(days=2), Room("Room 1", 5, 10), Decimal("9.50")))
        service.book_seat("s1", "alice", 2, 3)
        self.assertEqual(service.book_seat("s2", "bob", 2, 3).status, BookingStatus.ACTIVE)

    def test_booking_an_unknown_screening_is_rejected(self):
        service = self.make_service()
        with self.assertRaises(ScreeningNotFoundError):
            service.book_seat("nope", "alice", 1, 1)

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        service = self.make_service()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(InvalidSeatError):
                service.book_seat("s1", "alice", row, seat)
        # Corner seats are valid.
        service.book_seat("s1", "alice", 1, 1)
        service.book_seat("s1", "alice", 5, 10)

    def test_service_errors_share_a_common_base(self):
        service = self.make_service()
        with self.assertRaises(ProcessingException):
            service.book_seat("nope", "alice", 1, 1)

    # --- cancellation ----------------------------------------------------

    def test_cancelling_refunds_the_price_and_frees_the_seat(self):
        service = self.make_service()
        booking = service.book_seat("s1", "alice", 2, 3)
        cancelled = service.cancel_booking(booking.booking_id)
        self.assertEqual(cancelled.status, BookingStatus.CANCELLED)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.booking_id, Decimal("9.50"))])
        # The seat can be booked again.
        self.assertEqual(service.book_seat("s1", "bob", 2, 3).status, BookingStatus.ACTIVE)

    def test_cancelling_exactly_two_hours_before_is_allowed(self):
        service = self.make_service(starts_in=timedelta(hours=2))
        booking = service.book_seat("s1", "alice", 1, 1)
        self.assertEqual(service.cancel_booking(booking.booking_id).status, BookingStatus.CANCELLED)

    def test_cancelling_less_than_two_hours_before_is_rejected(self):
        service = self.make_service(starts_in=timedelta(hours=2) - timedelta(seconds=1))
        booking = service.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(CancellationDeadlinePassedError):
            service.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_cancelling_an_unknown_booking_is_rejected(self):
        service = self.make_service()
        with self.assertRaises(BookingNotFoundError):
            service.cancel_booking("nope")

    def test_cancelling_twice_is_rejected_and_refunds_once(self):
        service = self.make_service()
        booking = service.book_seat("s1", "alice", 1, 1)
        service.cancel_booking(booking.booking_id)
        with self.assertRaises(BookingAlreadyCancelledError):
            service.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    # --- refund via the gateway ------------------------------------------

    def test_transient_failures_are_retried_until_success(self):
        service = self.make_service(FakeGateway(*[GatewayTransientError("timeout")] * 3))
        booking = service.book_seat("s1", "alice", 1, 1)
        service.cancel_booking(booking.booking_id)
        # One attempt plus three retries.
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_transient_failures_beyond_three_retries_fail_the_refund(self):
        service = self.make_service(FakeGateway(*[GatewayTransientError("timeout")] * 4))
        booking = service.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError) as ctx:
            service.cancel_booking(booking.booking_id)
        self.assertIsInstance(ctx.exception.__cause__, GatewayTransientError)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.FAILED)

    def test_permanent_failure_keeps_the_booking_active(self):
        service = self.make_service(FakeGateway(GatewayPermanentError("card closed")))
        booking = service.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel_booking(booking.booking_id)
        # No retry on a permanent failure.
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.FAILED)
        # The seat is still held.
        with self.assertRaises(SeatAlreadyBookedError):
            service.book_seat("s1", "bob", 1, 1)

    def test_cancellation_can_be_retried_after_a_failed_refund(self):
        service = self.make_service(FakeGateway(GatewayPermanentError("card closed")))
        booking = service.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel_booking(booking.booking_id)
        service.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)

    def test_unavailable_gateway_rejects_the_cancellation(self):
        service = self.make_service(FakeGateway(GatewayUnavailableError("down")))
        booking = service.book_seat("s1", "alice", 1, 1)
        with self.assertRaises(RefundUnavailableError):
            service.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_refund_status_of_an_unknown_booking_is_rejected(self):
        service = self.make_service()
        with self.assertRaises(BookingNotFoundError):
            service.refund_status("nope")


if __name__ == "__main__":
    unittest.main()
