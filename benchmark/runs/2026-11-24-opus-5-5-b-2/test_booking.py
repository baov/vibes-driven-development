import logging
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from seat_booking.booking import (
    BookingAlreadyCancelledError,
    BookingManager,
    BookingNotFoundError,
    BookingStatus,
    CancellationInProgressError,
    CancellationWindowClosedError,
    GatewayUnavailableError,
    PaymentGatewayUnavailableError,
    PermanentGatewayError,
    RefundFailedError,
    RefundStatus,
    Room,
    ScreeningAlreadyStartedError,
    Screening,
    SeatAlreadyBookedError,
    SeatNotInRoomError,
    TransientGatewayError,
)

START = datetime(2026, 12, 1, 20, 0, tzinfo=timezone.utc)
ROOM = Room(name="Room 1", rows=5, seats_per_row=10)
SCREENING = Screening(id="S1", starts_at=START, room=ROOM, price=Decimal("12.50"))


class FakeGateway:
    """Plays back a scripted list of outcomes: None for success, or an exception to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount):
        self.calls.append((booking_id, amount))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome


class FakeClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class BookingTestCase(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.clock = FakeClock(START - timedelta(days=1))

    def manager(self, *gateway_outcomes):
        self.gateway = FakeGateway(*gateway_outcomes)
        return BookingManager(self.gateway, clock=self.clock)


class BookSeatTest(BookingTestCase):
    def test_books_a_free_seat(self):
        manager = self.manager()
        booking = manager.book(SCREENING, "alice", 2, 3)

        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual((booking.client_id, booking.row, booking.seat), ("alice", 2, 3))
        self.assertIs(manager.get_booking(booking.id), booking)
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.NOT_REQUESTED)

    def test_rejects_a_seat_already_booked(self):
        manager = self.manager()
        manager.book(SCREENING, "alice", 2, 3)

        with self.assertRaises(SeatAlreadyBookedError):
            manager.book(SCREENING, "bob", 2, 3)

    def test_same_seat_in_another_screening_is_independent(self):
        manager = self.manager()
        other = Screening(id="S2", starts_at=START, room=ROOM, price=Decimal("9"))
        manager.book(SCREENING, "alice", 2, 3)

        self.assertEqual(manager.book(other, "bob", 2, 3).status, BookingStatus.ACTIVE)

    def test_rejects_a_seat_outside_the_room(self):
        manager = self.manager()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(SeatNotInRoomError):
                manager.book(SCREENING, "alice", row, seat)

    def test_rejects_booking_once_the_screening_has_started(self):
        manager = self.manager()
        self.clock.now = START

        with self.assertRaises(ScreeningAlreadyStartedError):
            manager.book(SCREENING, "alice", 1, 1)

    def test_default_clock_is_timezone_aware_utc(self):
        manager = BookingManager(FakeGateway())
        future = Screening(
            id="S3",
            starts_at=datetime.now(timezone.utc) + timedelta(days=1),
            room=ROOM,
            price=Decimal("10"),
        )
        self.assertEqual(manager.book(future, "alice", 1, 1).status, BookingStatus.ACTIVE)


class CancelBookingTest(BookingTestCase):
    def test_cancels_and_refunds_the_screening_price(self):
        manager = self.manager()
        booking = manager.book(SCREENING, "alice", 1, 1)

        manager.cancel(booking.id)

        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(booking.id, Decimal("12.50"))])

    def test_cancelled_seat_can_be_booked_again(self):
        manager = self.manager()
        manager.cancel(manager.book(SCREENING, "alice", 1, 1).id)

        self.assertEqual(manager.book(SCREENING, "bob", 1, 1).client_id, "bob")

    def test_can_cancel_exactly_two_hours_before_start(self):
        manager = self.manager()
        booking = manager.book(SCREENING, "alice", 1, 1)
        self.clock.now = START - timedelta(hours=2)

        manager.cancel(booking.id)

        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_rejects_cancellation_less_than_two_hours_before_start(self):
        manager = self.manager()
        booking = manager.book(SCREENING, "alice", 1, 1)
        self.clock.now = START - timedelta(hours=2) + timedelta(seconds=1)

        with self.assertRaises(CancellationWindowClosedError):
            manager.cancel(booking.id)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_rejects_cancelling_twice(self):
        manager = self.manager()
        booking = manager.book(SCREENING, "alice", 1, 1)
        manager.cancel(booking.id)

        with self.assertRaises(BookingAlreadyCancelledError):
            manager.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_rejects_unknown_booking(self):
        manager = self.manager()
        with self.assertRaises(BookingNotFoundError):
            manager.cancel("nope")
        with self.assertRaises(BookingNotFoundError):
            manager.refund_status("nope")

    def test_rejects_cancellation_while_a_refund_is_in_flight(self):
        manager = self.manager()
        booking = manager.book(SCREENING, "alice", 1, 1)
        seen = []

        def reentrant_refund(booking_id, amount):
            # A second cancellation arriving while the gateway call is in progress.
            with self.assertRaises(CancellationInProgressError):
                manager.cancel(booking_id)
            seen.append(manager.refund_status(booking_id))

        self.gateway.refund = reentrant_refund
        manager.cancel(booking.id)

        self.assertEqual(seen, [RefundStatus.PENDING])
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.REFUNDED)


class RefundFailureTest(BookingTestCase):
    def test_transient_failures_are_retried_until_success(self):
        manager = self.manager(TransientGatewayError(), TransientGatewayError(), TransientGatewayError())
        booking = manager.book(SCREENING, "alice", 1, 1)

        manager.cancel(booking.id)

        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.REFUNDED)

    def test_gives_up_after_three_retries(self):
        manager = self.manager(*[TransientGatewayError() for _ in range(4)])
        booking = manager.book(SCREENING, "alice", 1, 1)

        with self.assertRaises(RefundFailedError):
            manager.cancel(booking.id)

        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.FAILED)

    def test_permanent_failure_keeps_booking_active_without_retrying(self):
        manager = self.manager(PermanentGatewayError("card closed"))
        booking = manager.book(SCREENING, "alice", 1, 1)

        with self.assertRaises(RefundFailedError) as ctx:
            manager.cancel(booking.id)

        self.assertIsInstance(ctx.exception.__cause__, PermanentGatewayError)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.FAILED)
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book(SCREENING, "bob", 1, 1)

    def test_failed_refund_can_be_retried_by_cancelling_again(self):
        manager = self.manager(PermanentGatewayError(), None)
        booking = manager.book(SCREENING, "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            manager.cancel(booking.id)

        manager.cancel(booking.id)

        self.assertEqual(manager.refund_status(booking.id), RefundStatus.REFUNDED)

    def test_unavailable_gateway_rejects_cancellation_and_changes_nothing(self):
        manager = self.manager(GatewayUnavailableError())
        booking = manager.book(SCREENING, "alice", 1, 1)

        with self.assertRaises(PaymentGatewayUnavailableError):
            manager.cancel(booking.id)

        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(manager.refund_status(booking.id), RefundStatus.NOT_REQUESTED)

    def test_unavailable_after_a_previous_failure_keeps_failed_status(self):
        manager = self.manager(PermanentGatewayError(), GatewayUnavailableError())
        booking = manager.book(SCREENING, "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            manager.cancel(booking.id)

        with self.assertRaises(PaymentGatewayUnavailableError):
            manager.cancel(booking.id)

        self.assertEqual(manager.refund_status(booking.id), RefundStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
