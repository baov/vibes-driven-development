import unittest
from datetime import datetime, timedelta

from seat_booking import (
    BookingAlreadyCancelledException, BookingManager, BookingNotFoundException,
    CancellationTooLateException, GatewayUnavailableError, InvalidBookingRequestException,
    PermanentGatewayError, ProcessingException, RefundFailedException,
    RefundUnavailableException, Room, Screening, SeatAlreadyBookedException,
    TransientGatewayError,
)

START = datetime(2026, 12, 1, 20, 0)


# Fake gateway: plays back scripted outcomes, records calls.
class FakeGateway:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.calls = []

    def refund(self, booking_id, amount_cents):
        self.calls.append((booking_id, amount_cents))
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if outcome is not None:
                raise outcome


class BookingManagerTest(unittest.TestCase):
    def setUp(self):
        self.now = START - timedelta(days=1)
        self.gateway = FakeGateway()
        self.manager = BookingManager(self.gateway, clock=lambda: self.now)
        self.manager.add_screening(Screening("S1", START, Room(5, 10), 1250))

    def test_book_seat(self):
        booking = self.manager.book_seat("alice", "S1", 2, 3)
        self.assertEqual((booking.row, booking.seat, booking.price_cents), (2, 3, 1250))
        self.assertEqual(booking.status, "ACTIVE")
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), "NONE")

    def test_book_seat_already_booked_is_rejected(self):
        self.manager.book_seat("alice", "S1", 2, 3)
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("bob", "S1", 2, 3)

    def test_book_other_seat_and_other_screening_allowed(self):
        self.manager.add_screening(Screening("S2", START, Room(5, 10), 900))
        self.manager.book_seat("alice", "S1", 2, 3)
        self.manager.book_seat("bob", "S1", 2, 4)
        self.manager.book_seat("bob", "S2", 2, 3)

    def test_book_seat_invalid_requests(self):
        for args in [("S9", 1, 1), ("S1", 0, 1), ("S1", 6, 1), ("S1", 1, 0), ("S1", 1, 11)]:
            with self.assertRaises(InvalidBookingRequestException):
                self.manager.book_seat("alice", *args)

    def test_book_seat_after_start_is_rejected(self):
        self.now = START
        with self.assertRaises(InvalidBookingRequestException):
            self.manager.book_seat("alice", "S1", 1, 1)

    def test_book_seat_unexpected_error_is_wrapped(self):
        with self.assertRaises(ProcessingException) as ctx:
            self.manager.book_seat("alice", "S1", None, 1)
        self.assertIs(type(ctx.exception), ProcessingException)

    def test_cancel_booking_refunds_and_frees_seat(self):
        booking = self.manager.book_seat("alice", "S1", 2, 3)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, "CANCELLED")
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), "REFUNDED")
        self.assertEqual(self.gateway.calls, [(booking.booking_id, 1250)])
        self.manager.book_seat("bob", "S1", 2, 3)

    def test_cancel_exactly_two_hours_before_is_allowed(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.now = START - timedelta(hours=2)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, "CANCELLED")

    def test_cancel_less_than_two_hours_before_is_rejected(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.now = START - timedelta(hours=2) + timedelta(seconds=1)
        with self.assertRaises(CancellationTooLateException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, "ACTIVE")
        self.assertEqual(self.gateway.calls, [])

    def test_cancel_unknown_booking_is_rejected(self):
        with self.assertRaises(BookingNotFoundException):
            self.manager.cancel_booking("nope")

    def test_cancel_twice_is_rejected_and_refunds_once(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.manager.cancel_booking(booking.booking_id)
        with self.assertRaises(BookingAlreadyCancelledException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_transient_failures_are_retried_up_to_three_times(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.gateway.outcomes = [TransientGatewayError()] * 3 + [None]
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, "CANCELLED")

    def test_transient_failures_exhausted_keep_booking_active(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.gateway.outcomes = [TransientGatewayError()] * 10
        with self.assertRaises(RefundFailedException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 4)
        self.assertEqual(booking.status, "ACTIVE")
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), "FAILED")

    def test_permanent_failure_keeps_booking_active_without_retry(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.gateway.outcomes = [PermanentGatewayError()]
        with self.assertRaises(RefundFailedException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(booking.status, "ACTIVE")
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), "FAILED")

    def test_gateway_unavailable_rejects_cancellation(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.gateway.outcomes = [GatewayUnavailableError()]
        with self.assertRaises(RefundUnavailableException):
            self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(booking.status, "ACTIVE")
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), "UNAVAILABLE")

    def test_cancel_unexpected_error_is_wrapped(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.gateway.outcomes = [RuntimeError("boom")]
        with self.assertRaises(ProcessingException) as ctx:
            self.manager.cancel_booking(booking.booking_id)
        self.assertIs(type(ctx.exception), ProcessingException)

    def test_get_refund_status_unknown_booking_is_rejected(self):
        with self.assertRaises(BookingNotFoundException):
            self.manager.get_refund_status("nope")

    def test_failed_refund_can_be_retried_later(self):
        booking = self.manager.book_seat("alice", "S1", 1, 1)
        self.gateway.outcomes = [PermanentGatewayError()]
        with self.assertRaises(RefundFailedException):
            self.manager.cancel_booking(booking.booking_id)
        self.manager.cancel_booking(booking.booking_id)
        self.assertEqual(self.manager.get_refund_status(booking.booking_id), "REFUNDED")


if __name__ == "__main__":
    unittest.main()
