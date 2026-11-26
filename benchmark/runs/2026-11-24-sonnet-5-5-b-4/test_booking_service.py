# Unit test framework.
import unittest
# Mocks for collaborators.
from unittest.mock import MagicMock
# Date arithmetic.
from datetime import datetime, timedelta

# Class under test and collaborators' types.
from seat_booking import (BookingService, ProcessingException, TransientGatewayError,
                          PermanentGatewayError, GatewayUnavailableError,
                          BOOKING_ACTIVE, BOOKING_CANCELLED, REFUND_NOT_REQUESTED,
                          REFUND_REFUNDED, REFUND_FAILED, REFUND_UNAVAILABLE)

# Fixed "now" used by every test.
NOW = datetime(2026, 1, 1, 12, 0)


# Mirror test of BookingService; gateway and screening are mocked.
class BookingServiceTest(unittest.TestCase):
    # Build a service with a mocked gateway and a fixed clock.
    def make_service(self):
        # Mocked gateway.
        gateway = MagicMock()
        # Service under test, plus its gateway.
        return BookingService(gateway, clock=lambda: NOW), gateway

    # Build a mocked screening starting after the given delay.
    def make_screening(self, delay):
        # Mocked screening.
        screening = MagicMock()
        # Start time.
        screening.start_time = NOW + delay
        # Room layout.
        screening.room.rows = 3
        # Seats per row.
        screening.room.seats_per_row = 4
        # Price.
        screening.price = 10.0
        # Return it.
        return screening

    # Book a seat then return the pieces.
    def booked(self, delay=timedelta(hours=5)):
        # Service and gateway.
        service, gateway = self.make_service()
        # Screening.
        screening = self.make_screening(delay)
        # Book and return everything.
        return service, gateway, service.book_seat("c1", screening, 1, 1)

    # book_seat: nominal case.
    def test_book_seat(self):
        # Book.
        service, gateway, result = self.booked()
        # Stored and active.
        self.assertEqual((BOOKING_ACTIVE, result), (result.status, service.bookings[result.booking_id]))

    # book_seat: double booking rejected.
    def test_book_seat2(self):
        # Book once.
        service, gateway, first = self.booked()
        # Booking the same seat again is rejected.
        with self.assertRaises(ProcessingException) as caught:
            service.book_seat("c2", first.screening, 1, 1)
        # Reason.
        self.assertEqual("SEAT_ALREADY_BOOKED", caught.exception.reason)

    # book_seat: another seat is fine, unknown seats and started screenings are not.
    def test_book_seat3(self):
        # Book once.
        service, gateway, first = self.booked()
        # Another seat works.
        self.assertEqual("B2", service.book_seat("c2", first.screening, 1, 2).booking_id)
        # Seat outside the room.
        with self.assertRaises(ProcessingException) as caught:
            service.book_seat("c2", first.screening, 9, 1)
        # Reason.
        self.assertEqual("UNKNOWN_SEAT", caught.exception.reason)
        # Started screening.
        with self.assertRaises(ProcessingException) as started:
            service.book_seat("c2", self.make_screening(timedelta(hours=-1)), 1, 1)
        # Reason.
        self.assertEqual("SCREENING_STARTED", started.exception.reason)

    # book_seat: unexpected errors are wrapped without cause.
    def test_book_seat4(self):
        # Clock that blows up.
        service = BookingService(MagicMock(), clock=MagicMock(side_effect=RuntimeError("boom")))
        # Wrapped.
        with self.assertRaises(ProcessingException) as caught:
            service.book_seat("c1", self.make_screening(timedelta(hours=5)), 1, 1)
        # Cause omitted.
        self.assertIsNone(caught.exception.__cause__)

    # cancel_booking: nominal case refunds the booking and frees the seat.
    def test_cancel_booking(self):
        # Book.
        service, gateway, booking = self.booked()
        # Cancel.
        service.cancel_booking(booking.booking_id)
        # Gateway called once with id and price.
        gateway.refund.assert_called_once_with(booking.booking_id, 10.0)
        # States.
        self.assertEqual((BOOKING_CANCELLED, REFUND_REFUNDED), (booking.status, booking.refund_status))
        # Seat bookable again.
        service.book_seat("c2", booking.screening, 1, 1)

    # cancel_booking: unknown, already cancelled and too late are rejected.
    def test_cancel_booking2(self):
        # Book.
        service, gateway, booking = self.booked()
        # Unknown.
        with self.assertRaises(ProcessingException) as unknown:
            service.cancel_booking("nope")
        # Reason.
        self.assertEqual("UNKNOWN_BOOKING", unknown.exception.reason)
        # Cancel once.
        service.cancel_booking(booking.booking_id)
        # Cancel again.
        with self.assertRaises(ProcessingException) as again:
            service.cancel_booking(booking.booking_id)
        # Reason.
        self.assertEqual("ALREADY_CANCELLED", again.exception.reason)
        # Less than two hours before start.
        late = service.book_seat("c1", self.make_screening(timedelta(hours=1, minutes=59)), 1, 1)
        # Rejected.
        with self.assertRaises(ProcessingException) as too_late:
            service.cancel_booking(late.booking_id)
        # Reason.
        self.assertEqual("TOO_LATE", too_late.exception.reason)
        # Exactly two hours is still allowed.
        edge = service.book_seat("c1", self.make_screening(timedelta(hours=2)), 1, 1)
        # Cancel it.
        service.cancel_booking(edge.booking_id)

    # cancel_booking: transient failures are retried up to three times.
    def test_cancel_booking3(self):
        # Book.
        service, gateway, booking = self.booked()
        # Fail three times then succeed: 4 calls in total.
        gateway.refund.side_effect = [TransientGatewayError()] * 3 + [None]
        # Cancel.
        service.cancel_booking(booking.booking_id)
        # Four calls, cancelled.
        self.assertEqual((4, BOOKING_CANCELLED), (gateway.refund.call_count, booking.status))

    # cancel_booking: retries exhausted keeps the booking active.
    def test_cancel_booking4(self):
        # Book.
        service, gateway, booking = self.booked()
        # Always transient.
        gateway.refund.side_effect = TransientGatewayError()
        # Rejected.
        with self.assertRaises(ProcessingException):
            service.cancel_booking(booking.booking_id)
        # Four calls, still active.
        self.assertEqual((4, BOOKING_ACTIVE, REFUND_FAILED),
                         (gateway.refund.call_count, booking.status, booking.refund_status))

    # cancel_booking: permanent failure keeps the booking active, no retry.
    def test_cancel_booking5(self):
        # Book.
        service, gateway, booking = self.booked()
        # Permanent failure.
        gateway.refund.side_effect = PermanentGatewayError()
        # Rejected.
        with self.assertRaises(ProcessingException):
            service.cancel_booking(booking.booking_id)
        # One call, still active.
        self.assertEqual((1, BOOKING_ACTIVE, REFUND_FAILED),
                         (gateway.refund.call_count, booking.status, booking.refund_status))

    # cancel_booking: unavailable gateway rejects the cancellation.
    def test_cancel_booking6(self):
        # Book.
        service, gateway, booking = self.booked()
        # Gateway down.
        gateway.refund.side_effect = GatewayUnavailableError()
        # Rejected.
        with self.assertRaises(ProcessingException) as caught:
            service.cancel_booking(booking.booking_id)
        # Reason and states.
        self.assertEqual(("GATEWAY_UNAVAILABLE", BOOKING_ACTIVE, REFUND_UNAVAILABLE),
                         (caught.exception.reason, booking.status, booking.refund_status))

    # cancel_booking: unexpected errors are wrapped without cause.
    def test_cancel_booking7(self):
        # Book.
        service, gateway, booking = self.booked()
        # Unexpected gateway error.
        gateway.refund.side_effect = RuntimeError("boom")
        # Wrapped.
        with self.assertRaises(ProcessingException) as caught:
            service.cancel_booking(booking.booking_id)
        # Cause omitted.
        self.assertIsNone(caught.exception.__cause__)

    # get_refund_status: initial status, refunded status and unknown booking.
    def test_get_refund_status(self):
        # Book.
        service, gateway, booking = self.booked()
        # Status before any refund.
        self.assertEqual(REFUND_NOT_REQUESTED, service.get_refund_status(booking.booking_id))
        # Cancel.
        service.cancel_booking(booking.booking_id)
        # Status after refund.
        self.assertEqual(REFUND_REFUNDED, service.get_refund_status(booking.booking_id))
        # Unknown booking.
        with self.assertRaises(ProcessingException):
            service.get_refund_status("nope")
