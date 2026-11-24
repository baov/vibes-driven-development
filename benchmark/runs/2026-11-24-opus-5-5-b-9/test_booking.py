import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from seat_booking.booking import (
    BookingAlreadyCancelledError,
    BookingService,
    BookingStatus,
    CancellationDeadlinePassedError,
    CancellationInProgressError,
    GatewayUnavailableError,
    InvalidSeatError,
    NotBookingOwnerError,
    PermanentRefundError,
    RefundFailedError,
    RefundStatus,
    RefundUnavailableError,
    Room,
    ScreeningAlreadyStartedError,
    Screening,
    SeatAlreadyBookedError,
    TransientRefundError,
    UnknownBookingError,
    UnknownScreeningError,
)

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)


class FakeGateway:
    """Replays a script of outcomes: None for success, or an exception."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount):
        self.calls.append((booking_id, amount))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome


class BookingServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.gateway = FakeGateway()
        self.service = BookingService(self.gateway, clock=lambda: self.now)
        self.screening = Screening(
            screening_id="S1",
            starts_at=NOW + timedelta(hours=5),
            room=Room(name="Room 1", rows=3, seats_per_row=4),
            price=Decimal("12.50"),
        )
        self.service.add_screening(self.screening)

    def use_gateway(self, *outcomes):
        self.gateway = FakeGateway(*outcomes)
        self.service._gateway = self.gateway


class BookTest(BookingServiceTestCase):
    def test_books_a_free_seat_at_the_screening_price(self):
        booking = self.service.book("S1", "alice", 2, 3)

        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(booking.amount, Decimal("12.50"))
        self.assertEqual((booking.row, booking.seat), (2, 3))
        self.assertEqual(self.service.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_rejects_a_seat_already_booked(self):
        self.service.book("S1", "alice", 1, 1)

        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("S1", "bob", 1, 1)

    def test_same_seat_at_another_screening_is_independent(self):
        self.service.add_screening(Screening("S2", NOW + timedelta(hours=5), self.screening.room, Decimal("10")))
        self.service.book("S1", "alice", 1, 1)

        self.assertEqual(self.service.book("S2", "bob", 1, 1).screening_id, "S2")

    def test_rejects_unknown_screening(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", 1, 1)

    def test_rejects_seat_outside_the_room(self):
        for row, seat in [(0, 1), (4, 1), (1, 0), (1, 5)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(InvalidSeatError):
                self.service.book("S1", "alice", row, seat)

    def test_rejects_booking_once_the_screening_started(self):
        self.now = self.screening.starts_at

        with self.assertRaises(ScreeningAlreadyStartedError):
            self.service.book("S1", "alice", 1, 1)


class CancelTest(BookingServiceTestCase):
    def setUp(self):
        super().setUp()
        self.booking = self.service.book("S1", "alice", 1, 1)

    def test_cancels_and_refunds_the_paid_amount(self):
        self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.booking.status, BookingStatus.CANCELLED)
        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.gateway.calls, [(self.booking.booking_id, Decimal("12.50"))])

    def test_cancelled_seat_can_be_booked_again(self):
        self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.service.book("S1", "bob", 1, 1).client_id, "bob")

    def test_allows_cancellation_exactly_two_hours_before_start(self):
        self.now = self.screening.starts_at - timedelta(hours=2)

        self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.booking.status, BookingStatus.CANCELLED)

    def test_rejects_cancellation_less_than_two_hours_before_start(self):
        self.now = self.screening.starts_at - timedelta(hours=2) + timedelta(seconds=1)

        with self.assertRaises(CancellationDeadlinePassedError):
            self.service.cancel(self.booking.booking_id, "alice")
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.gateway.calls, [])

    def test_rejects_cancelling_an_already_cancelled_booking(self):
        self.service.cancel(self.booking.booking_id, "alice")

        with self.assertRaises(BookingAlreadyCancelledError):
            self.service.cancel(self.booking.booking_id, "alice")
        self.assertEqual(len(self.gateway.calls), 1)

    def test_rejects_cancelling_an_unknown_booking(self):
        with self.assertRaises(UnknownBookingError):
            self.service.cancel("B999", "alice")

    def test_rejects_cancellation_by_another_client(self):
        with self.assertRaises(NotBookingOwnerError):
            self.service.cancel(self.booking.booking_id, "mallory")
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)

    def test_retries_transient_failures_then_succeeds(self):
        self.use_gateway(TransientRefundError(), TransientRefundError(), TransientRefundError(), None)

        self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.booking.status, BookingStatus.CANCELLED)

    def test_gives_up_after_three_retries(self):
        self.use_gateway(*[TransientRefundError() for _ in range(5)])

        with self.assertRaises(RefundFailedError):
            self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.FAILED)
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        self.use_gateway(PermanentRefundError("card closed"))

        with self.assertRaises(RefundFailedError):
            self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.FAILED)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("S1", "bob", 1, 1)

    def test_unavailable_gateway_rejects_cancellation(self):
        self.use_gateway(GatewayUnavailableError())

        with self.assertRaises(RefundUnavailableError):
            self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_unavailable_gateway_after_transient_failure_rejects_cancellation(self):
        self.use_gateway(TransientRefundError(), GatewayUnavailableError())

        with self.assertRaises(RefundUnavailableError):
            self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)
        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.NOT_REQUESTED)

    def test_cancellation_can_be_retried_after_a_failed_refund(self):
        self.use_gateway(PermanentRefundError(), None)
        with self.assertRaises(RefundFailedError):
            self.service.cancel(self.booking.booking_id, "alice")

        self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.REFUNDED)
        self.assertEqual(self.booking.status, BookingStatus.CANCELLED)

    def test_rejects_second_cancellation_while_refund_is_in_flight(self):
        service, booking_id, seen = self.service, self.booking.booking_id, []

        class ReentrantGateway:
            def refund(self, booking_id_, amount):
                seen.append(service.get_refund_status(booking_id))
                with self_test.assertRaises(CancellationInProgressError):
                    service.cancel(booking_id, "alice")

        self_test = self
        self.service._gateway = ReentrantGateway()

        self.service.cancel(booking_id, "alice")

        self.assertEqual(seen, [RefundStatus.PENDING])
        self.assertEqual(self.service.get_refund_status(booking_id), RefundStatus.REFUNDED)

    def test_unexpected_gateway_error_marks_refund_failed(self):
        self.use_gateway(RuntimeError("boom"))

        with self.assertRaises(RuntimeError):
            self.service.cancel(self.booking.booking_id, "alice")

        self.assertEqual(self.service.get_refund_status(self.booking.booking_id), RefundStatus.FAILED)
        self.assertEqual(self.booking.status, BookingStatus.ACTIVE)


class RefundStatusTest(BookingServiceTestCase):
    def test_rejects_unknown_booking(self):
        with self.assertRaises(UnknownBookingError):
            self.service.get_refund_status("B999")


if __name__ == "__main__":
    unittest.main()
