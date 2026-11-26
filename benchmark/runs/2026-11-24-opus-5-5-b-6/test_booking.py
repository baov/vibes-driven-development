import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from seat_booking.booking import (
    BookingAlreadyCancelledError,
    BookingNotFoundError,
    BookingService,
    BookingStatus,
    CancellationTooLateError,
    DuplicateScreeningError,
    GatewayUnavailableError,
    InvalidSeatError,
    MAX_REFUND_RETRIES,
    PermanentGatewayError,
    RefundFailedError,
    RefundStatus,
    RefundUnavailableError,
    Room,
    Screening,
    ScreeningNotFoundError,
    SeatAlreadyBookedError,
    TransientGatewayError,
)

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
PRICE = Decimal("11.50")


class FakeGateway:
    """Raises the scripted outcomes in order, then succeeds. Records every call."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount):
        self.calls.append((booking_id, amount))
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if outcome is not None:
                raise outcome


class BookingServiceTest(unittest.TestCase):
    def make_service(self, *gateway_outcomes, starts_in=timedelta(days=1)):
        self.gateway = FakeGateway(*gateway_outcomes)
        self.now = NOW
        service = BookingService(self.gateway, clock=lambda: self.now)
        service.add_screening(Screening("S1", NOW + starts_in, Room(rows=5, seats_per_row=10), PRICE))
        return service

    # --- booking ---

    def test_book_free_seat(self):
        service = self.make_service()
        booking = service.book("S1", "alice", 2, 3)
        self.assertEqual((booking.screening_id, booking.client_id, booking.row, booking.seat),
                         ("S1", "alice", 2, 3))
        self.assertEqual(booking.price, PRICE)
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.NOT_REQUESTED)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = self.make_service()
        service.book("S1", "alice", 2, 3)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("S1", "bob", 2, 3)

    def test_same_seat_in_another_screening_is_independent(self):
        service = self.make_service()
        service.add_screening(Screening("S2", NOW + timedelta(days=1), Room(5, 10), PRICE))
        service.book("S1", "alice", 2, 3)
        self.assertEqual(service.book("S2", "bob", 2, 3).screening_id, "S2")

    def test_booking_unknown_screening_is_rejected(self):
        service = self.make_service()
        with self.assertRaises(ScreeningNotFoundError):
            service.book("nope", "alice", 1, 1)

    def test_booking_seat_outside_room_is_rejected(self):
        service = self.make_service()
        for row, seat in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            with self.subTest(row=row, seat=seat), self.assertRaises(InvalidSeatError):
                service.book("S1", "alice", row, seat)

    def test_duplicate_screening_is_rejected(self):
        service = self.make_service()
        with self.assertRaises(DuplicateScreeningError):
            service.add_screening(Screening("S1", NOW, Room(1, 1), PRICE))

    def test_screening_validation(self):
        with self.assertRaises(ValueError):
            Room(0, 10)
        with self.assertRaises(ValueError):
            Screening("X", datetime(2026, 1, 1), Room(1, 1), PRICE)  # naive datetime
        with self.assertRaises(ValueError):
            Screening("X", NOW, Room(1, 1), Decimal("-1"))

    # --- cancellation ---

    def test_cancel_refunds_and_frees_the_seat(self):
        service = self.make_service()
        booking = service.book("S1", "alice", 2, 3)
        service.cancel(booking.id)
        self.assertEqual(self.gateway.calls, [(booking.id, PRICE)])
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.CANCELLED)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.REFUNDED)
        self.assertEqual(service.book("S1", "bob", 2, 3).client_id, "bob")

    def test_cancel_exactly_two_hours_before_is_allowed(self):
        service = self.make_service(starts_in=timedelta(hours=2))
        booking = service.book("S1", "alice", 1, 1)
        service.cancel(booking.id)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.REFUNDED)

    def test_cancel_less_than_two_hours_before_is_rejected(self):
        service = self.make_service(starts_in=timedelta(hours=2, seconds=-1))
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(CancellationTooLateError):
            service.cancel(booking.id)
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.ACTIVE)

    def test_cancel_after_time_passes_is_rejected(self):
        service = self.make_service(starts_in=timedelta(hours=3))
        booking = service.book("S1", "alice", 1, 1)
        self.now = NOW + timedelta(hours=1, minutes=1)
        with self.assertRaises(CancellationTooLateError):
            service.cancel(booking.id)

    def test_cancel_unknown_booking_is_rejected(self):
        service = self.make_service()
        with self.assertRaises(BookingNotFoundError):
            service.cancel("B999")
        with self.assertRaises(BookingNotFoundError):
            service.refund_status("B999")

    def test_cancel_twice_is_rejected_and_refunds_once(self):
        service = self.make_service()
        booking = service.book("S1", "alice", 1, 1)
        service.cancel(booking.id)
        with self.assertRaises(BookingAlreadyCancelledError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1)

    # --- refund failures ---

    def test_transient_failures_are_retried_until_success(self):
        service = self.make_service(*[TransientGatewayError()] * MAX_REFUND_RETRIES)
        booking = service.book("S1", "alice", 1, 1)
        service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1 + MAX_REFUND_RETRIES)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.REFUNDED)
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.CANCELLED)

    def test_transient_failures_beyond_retry_limit_fail_the_refund(self):
        service = self.make_service(*[TransientGatewayError()] * (MAX_REFUND_RETRIES + 1))
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.id)
        self.assertEqual(MAX_REFUND_RETRIES, 3)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.FAILED)
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.ACTIVE)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("S1", "bob", 1, 1)

    def test_permanent_failure_keeps_booking_active(self):
        service = self.make_service(PermanentGatewayError())
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1)  # not retried
        self.assertEqual(service.refund_status(booking.id), RefundStatus.FAILED)
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.ACTIVE)
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("S1", "bob", 1, 1)

    def test_cancel_can_be_retried_after_a_failed_refund(self):
        service = self.make_service(PermanentGatewayError(), None)
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundFailedError):
            service.cancel(booking.id)
        service.cancel(booking.id)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.REFUNDED)

    def test_unavailable_gateway_rejects_cancellation(self):
        service = self.make_service(GatewayUnavailableError())
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundUnavailableError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(service.refund_status(booking.id), RefundStatus.NOT_REQUESTED)
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.ACTIVE)

    def test_unavailable_after_transient_failure_rejects_cancellation(self):
        service = self.make_service(TransientGatewayError(), GatewayUnavailableError())
        booking = service.book("S1", "alice", 1, 1)
        with self.assertRaises(RefundUnavailableError):
            service.cancel(booking.id)
        self.assertEqual(len(self.gateway.calls), 2)
        self.assertEqual(service.get_booking(booking.id).status, BookingStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
