"""Behaviour tests for seat_booking, one test per requirement.

The payment gateway is the only test double: it is the external boundary.
Everything else runs for real.
"""

# Import datetime helpers to build screening times and a fixed clock.
from datetime import datetime, timedelta, timezone
# Import Decimal for exact prices.
from decimal import Decimal
# Import unittest as the test framework.
import unittest

# Import the module under test.
from seat_booking import (
    BookingAlreadyCancelledError,
    BookingService,
    CancellationWindowClosedError,
    GatewayUnavailableError,
    InvalidSeatError,
    PermanentRefundError,
    RefundFailedError,
    RefundStatus,
    RefundUnavailableError,
    Room,
    Screening,
    SeatAlreadyBookedError,
    TransientRefundError,
    UnknownBookingError,
    UnknownScreeningError,
)

# Fix "now" so the cancellation window is deterministic.
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)


# Simulate the payment gateway by replaying a scripted list of outcomes.
class ScriptedGateway:

    # Store the outcomes (None = success, exception = raised) and the calls.
    def __init__(self, *outcomes):
        # Keep the remaining outcomes in order.
        self.outcomes = list(outcomes)
        # Record every refund call.
        self.calls = []

    # Record the call, then succeed or raise according to the script.
    def refund(self, booking_id, amount):
        # Record the call arguments.
        self.calls.append((booking_id, amount))
        # Take the next outcome, defaulting to success.
        outcome = self.outcomes.pop(0) if self.outcomes else None
        # Raise the scripted error, if any.
        if outcome is not None:
            # Raise the scripted error.
            raise outcome


# Exercise the booking, cancellation and refund rules.
class BookingServiceTest(unittest.TestCase):

    # Build a service with a 3x4 room and a screening starting in 3 hours.
    def make_service(self, gateway=None, starts_in=timedelta(hours=3)):
        # Default to a gateway that always succeeds.
        self.gateway = gateway or ScriptedGateway()
        # Create the service with a fixed clock.
        service = BookingService(self.gateway, clock=lambda: NOW)
        # Register the screening.
        service.add_screening(Screening("s1", NOW + starts_in, Room("Room 1", rows=3, seats_per_row=4), Decimal("9.50")))
        # Return the ready service.
        return service

    # A client books a free seat at the screening price.
    def test_book_free_seat(self):
        # Build the service.
        service = self.make_service()
        # Book row 2 seat 3.
        booking = service.book_seat("alice", "s1", 2, 3)
        # Check the booking contents.
        self.assertEqual((booking.client_id, booking.row, booking.seat, booking.price), ("alice", 2, 3, Decimal("9.50")))
        # Check the booking is active with no refund yet.
        self.assertFalse(booking.cancelled)
        # Check the exposed refund status.
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    # Booking an already booked seat is rejected, even by the same client.
    def test_book_already_booked_seat_is_rejected(self):
        # Build the service.
        service = self.make_service()
        # Book the seat once.
        service.book_seat("alice", "s1", 1, 1)
        # Check that a second booking by someone else is rejected.
        with self.assertRaises(SeatAlreadyBookedError):
            # Try to book the same seat.
            service.book_seat("bob", "s1", 1, 1)
        # Check that a second booking by the same client is rejected too.
        with self.assertRaises(SeatAlreadyBookedError):
            # Try to book the same seat again.
            service.book_seat("alice", "s1", 1, 1)
        # Check that a different seat is still bookable.
        service.book_seat("bob", "s1", 1, 2)

    # Unknown screenings and seats outside the room are rejected.
    def test_book_invalid_target_is_rejected(self):
        # Build the service.
        service = self.make_service()
        # Check the unknown screening.
        with self.assertRaises(UnknownScreeningError):
            # Book for an unknown screening.
            service.book_seat("alice", "nope", 1, 1)
        # Check rows and seats outside the 3x4 grid.
        for row, seat in [(0, 1), (4, 1), (1, 0), (1, 5)]:
            # Isolate each case in the report.
            with self.subTest(row=row, seat=seat):
                # Check the rejection.
                with self.assertRaises(InvalidSeatError):
                    # Book the out-of-range seat.
                    service.book_seat("alice", "s1", row, seat)

    # A successful cancellation refunds the price, cancels the booking and frees the seat.
    def test_cancel_refunds_and_frees_seat(self):
        # Build the service.
        service = self.make_service()
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Cancel it.
        service.cancel_booking(booking.booking_id)
        # Check the gateway was asked for the exact price.
        self.assertEqual(self.gateway.calls, [(booking.booking_id, Decimal("9.50"))])
        # Check the booking is cancelled.
        self.assertTrue(booking.cancelled)
        # Check the exposed refund status.
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)
        # Check the seat can be booked again.
        service.book_seat("bob", "s1", 1, 1)

    # Cancelling exactly two hours before the start is allowed; one second later is not.
    def test_cancel_two_hour_boundary(self):
        # Build a service whose screening starts in exactly 2 hours.
        service = self.make_service(starts_in=timedelta(hours=2))
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Check the cancellation succeeds at the boundary.
        service.cancel_booking(booking.booking_id)
        # Check the refund happened.
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.REFUNDED)

        # Build a service whose screening starts one second too soon.
        service = self.make_service(starts_in=timedelta(hours=2) - timedelta(seconds=1))
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Check the cancellation is rejected.
        with self.assertRaises(CancellationWindowClosedError):
            # Try to cancel.
            service.cancel_booking(booking.booking_id)
        # Check no refund was attempted and the booking is still active.
        self.assertEqual((self.gateway.calls, booking.cancelled), ([], False))
        # Check the exposed refund status.
        self.assertEqual(service.refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)

    # Cancelling an unknown or already cancelled booking is rejected without a second refund.
    def test_cancel_unknown_or_cancelled_booking_is_rejected(self):
        # Build the service.
        service = self.make_service()
        # Check the unknown booking.
        with self.assertRaises(UnknownBookingError):
            # Cancel an unknown id.
            service.cancel_booking("nope")
        # Check the refund status of an unknown booking.
        with self.assertRaises(UnknownBookingError):
            # Ask for an unknown id.
            service.refund_status("nope")
        # Book and cancel a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Cancel once.
        service.cancel_booking(booking.booking_id)
        # Check the second cancellation is rejected.
        with self.assertRaises(BookingAlreadyCancelledError):
            # Cancel again.
            service.cancel_booking(booking.booking_id)
        # Check only one refund was issued.
        self.assertEqual(len(self.gateway.calls), 1)

    # Transient failures are retried; success on the last allowed retry cancels the booking.
    def test_cancel_transient_failures_then_success(self):
        # Fail transiently three times, then succeed.
        service = self.make_service(ScriptedGateway(TransientRefundError(), TransientRefundError(), TransientRefundError(), None))
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Cancel it.
        service.cancel_booking(booking.booking_id)
        # Check four attempts were made (1 + 3 retries).
        self.assertEqual(len(self.gateway.calls), 4)
        # Check the booking is cancelled and refunded.
        self.assertEqual((booking.cancelled, service.refund_status(booking.booking_id)), (True, RefundStatus.REFUNDED))

    # Transient failures beyond three retries fail the refund and keep the booking active.
    def test_cancel_transient_failures_exhausted(self):
        # Fail transiently on every attempt.
        service = self.make_service(ScriptedGateway(*[TransientRefundError() for _ in range(5)]))
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Check the cancellation reports a failed refund.
        with self.assertRaises(RefundFailedError) as raised:
            # Try to cancel.
            service.cancel_booking(booking.booking_id)
        # Check the gateway error is kept as the cause.
        self.assertIsInstance(raised.exception.__cause__, TransientRefundError)
        # Check exactly four attempts were made.
        self.assertEqual(len(self.gateway.calls), 4)
        # Check the booking stays active with a failed refund.
        self.assertEqual((booking.cancelled, service.refund_status(booking.booking_id)), (False, RefundStatus.FAILED))
        # Check the seat is still taken.
        with self.assertRaises(SeatAlreadyBookedError):
            # Try to book the seat.
            service.book_seat("bob", "s1", 1, 1)

    # A permanent failure is not retried and keeps the booking active; a later cancel can succeed.
    def test_cancel_permanent_failure(self):
        # Fail permanently once, then succeed on the next call.
        service = self.make_service(ScriptedGateway(PermanentRefundError(), None))
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Check the cancellation reports a failed refund.
        with self.assertRaises(RefundFailedError) as raised:
            # Try to cancel.
            service.cancel_booking(booking.booking_id)
        # Check the gateway error is kept as the cause.
        self.assertIsInstance(raised.exception.__cause__, PermanentRefundError)
        # Check there was no retry.
        self.assertEqual(len(self.gateway.calls), 1)
        # Check the booking stays active with a failed refund.
        self.assertEqual((booking.cancelled, service.refund_status(booking.booking_id)), (False, RefundStatus.FAILED))
        # Retry the cancellation later.
        service.cancel_booking(booking.booking_id)
        # Check it now succeeds.
        self.assertEqual((booking.cancelled, service.refund_status(booking.booking_id)), (True, RefundStatus.REFUNDED))

    # An unavailable gateway rejects the cancellation and leaves the booking untouched.
    def test_cancel_gateway_unavailable(self):
        # Make the gateway unavailable.
        service = self.make_service(ScriptedGateway(GatewayUnavailableError()))
        # Book a seat.
        booking = service.book_seat("alice", "s1", 1, 1)
        # Check the cancellation is rejected.
        with self.assertRaises(RefundUnavailableError):
            # Try to cancel.
            service.cancel_booking(booking.booking_id)
        # Check there was no retry.
        self.assertEqual(len(self.gateway.calls), 1)
        # Check the booking is untouched.
        self.assertEqual((booking.cancelled, service.refund_status(booking.booking_id)), (False, RefundStatus.NOT_REQUESTED))


# Allow running this file directly.
if __name__ == "__main__":
    # Run the tests.
    unittest.main()
