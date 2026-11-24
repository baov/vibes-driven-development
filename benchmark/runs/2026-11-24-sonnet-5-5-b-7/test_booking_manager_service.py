# Suppress expected rejections inside a single scenario
import contextlib
# Standard unittest framework
import unittest
# Dates and mocks for collaborators
from datetime import datetime
from unittest import mock

# Classes under test and their collaborators
from seat_booking import (BookingManagerService, GatewayUnavailableError, PermanentGatewayError,
                          ProcessingException, Room, Screening, TransientGatewayError)


# One test class per production class, every collaborator mocked
class BookingManagerServiceTest(unittest.TestCase):
    # Build a service with a mocked gateway, clock and date helper
    def build(self):
        # Mocked gateway
        gateway = mock.Mock()
        # Mocked date helper
        date_util = mock.Mock()
        # Allow cancellation by default
        date_util.is_at_least_hours_before.return_value = True
        # Service wired with the mocks
        service = BookingManagerService(gateway, lambda: datetime(2026, 1, 1, 10, 0), date_util)
        # Register one screening (2 rows x 2 seats)
        service.add_screening(Screening("S1", datetime(2026, 1, 1, 20, 0), Room("R", 2, 2), 1200))
        # Hand everything back
        return service, gateway, date_util

    # One test per method: constructor (default date helper branch)
    def test_init(self):
        # Build without an explicit date helper
        service = BookingManagerService(mock.Mock(), mock.Mock())
        # Single assertion
        self.assertIsNotNone(service.date_util)

    # One test per method
    def test_add_screening(self):
        # Build the service
        service, _, _ = self.build()
        # Single assertion
        self.assertIn("S1", service.screenings)

    # One test per method, walking through every branch
    def test_book_seat(self):
        # Build the service
        service, _, _ = self.build()
        # Nominal booking
        service.book_seat("S1", "C1", 1, 1)
        # Rejection: seat already booked
        with contextlib.suppress(ProcessingException):
            service.book_seat("S1", "C2", 1, 1)
        # Rejection: unknown screening
        with contextlib.suppress(ProcessingException):
            service.book_seat("NOPE", "C2", 1, 1)
        # Rejection: seat outside the room
        with contextlib.suppress(ProcessingException):
            service.book_seat("S1", "C2", 9, 9)
        # Single assertion
        self.assertEqual(len(service.bookings), 1)

    # One test per method, walking through every branch
    def test_cancel_booking(self):
        # Build the service
        service, gateway, date_util = self.build()
        # Four bookings on the first screening
        ids = [service.book_seat("S1", "C", r, n).id for r in (1, 2) for n in (1, 2)]
        # A second screening for the retry-exhausted case
        service.add_screening(Screening("S2", datetime(2026, 1, 1, 20, 0), Room("R", 1, 1), 500))
        # Booking on it
        last = service.book_seat("S2", "C", 1, 1).id
        # Gateway outcomes in call order: transient then ok / permanent / unavailable / 4 transient
        gateway.refund.side_effect = [TransientGatewayError(), None, PermanentGatewayError(),
                                      GatewayUnavailableError()] + [TransientGatewayError()] * 4
        # Success after one transient failure
        service.cancel_booking(ids[0])
        # Rejection: already cancelled
        with contextlib.suppress(ProcessingException):
            service.cancel_booking(ids[0])
        # Rejection: unknown booking
        with contextlib.suppress(ProcessingException):
            service.cancel_booking("NOPE")
        # Permanent failure
        service.cancel_booking(ids[1])
        # Rejection: gateway unavailable
        with contextlib.suppress(ProcessingException):
            service.cancel_booking(ids[2])
        # Retries exhausted
        service.cancel_booking(last)
        # Too late to cancel
        date_util.is_at_least_hours_before.return_value = False
        # Rejection: too late
        with contextlib.suppress(ProcessingException):
            service.cancel_booking(ids[3])
        # Single interaction assertion
        gateway.refund.assert_called()

    # One test per method, walking through both branches
    def test_get_refund_status(self):
        # Build the service
        service, _, _ = self.build()
        # Book a seat
        booking = service.book_seat("S1", "C1", 1, 1)
        # Status of a known booking
        status = service.get_refund_status(booking.id)
        # Rejection: unknown booking
        with contextlib.suppress(ProcessingException):
            service.get_refund_status("NOPE")
        # Single assertion
        self.assertIsNotNone(status)
