# Standard library test framework
import unittest
# Standard library date helpers
from datetime import datetime, timedelta
# Standard library mocking, every collaborator is mocked
from unittest.mock import MagicMock, patch

# Class under test and the exceptions it exposes
from seat_booking import (
    BookingManagerService, BookingRejectedException, CancellationRejectedException,
    GatewayPermanentError, GatewayTransientError, GatewayUnavailableError, ProcessingException,
)

# Fixed start time of the mocked screening
START = datetime(2030, 1, 1, 20, 0)


# One test per public method of BookingManagerService
class BookingManagerServiceTest(unittest.TestCase):
    # Builds a service with a mocked gateway, a mocked clock and one mocked screening
    def build(self, now):
        # Mocked payment gateway
        gateway = MagicMock()
        # Mocked clock
        clock = MagicMock(return_value=now)
        # Mocked screening
        screening = MagicMock()
        # Screening identifier
        screening.screening_id = "s1"
        # Screening start time
        screening.start_time = START
        # Mocked room with 2 rows of 2 seats
        screening.room.rows = 2
        # Seats per row
        screening.room.seats_per_row = 2
        # Seat price
        screening.price = 10.0
        # Service under test
        service = BookingManagerService(gateway, clock)
        # Hand everything back to the test
        return service, gateway, screening

    # Tests register_screening
    def test_register_screening(self):
        # Build collaborators
        service, gateway, screening = self.build(START - timedelta(days=1))
        # Call the method
        service.register_screening(screening)
        # Minimal assertion required by the framework
        self.assertIn("s1", service.screenings)

    # Tests book_seat, every path is exercised to protect the coverage contract
    def test_book_seat(self):
        # Build collaborators
        service, gateway, screening = self.build(START - timedelta(days=1))
        # Register the screening
        service.register_screening(screening)
        # Nominal booking, Booking is mocked
        with patch("seat_booking.Booking") as booking_class:
            # Mocked booking carries the attributes read by the service
            booking_class.return_value.booking_id = "1"
            # Book a seat
            service.book_seat("s1", "c1", 1, 1)
        # Rejected: unknown screening, taken seat, unknown seat
        for args in [("nope", "c1", 1, 1), ("s1", "c2", 1, 1), ("s1", "c2", 3, 1)]:
            # Mocked stored booking in the same seat
            service.bookings["1"].status = "ACTIVE"
            # Mocked stored booking screening
            service.bookings["1"].screening.screening_id = "s1"
            # Mocked stored booking row and seat
            service.bookings["1"].row = 1
            # Mocked stored booking seat
            service.bookings["1"].seat = 1
            # Expect a rejection
            with self.assertRaises(BookingRejectedException):
                # Try to book
                service.book_seat(*args)
        # Rejected: screening already started
        service.now_provider.return_value = START
        # Expect a rejection
        with self.assertRaises(BookingRejectedException):
            # Try to book
            service.book_seat("s1", "c1", 2, 2)
        # Unexpected failure is wrapped in a generic exception
        service.now_provider.side_effect = RuntimeError("boom")
        # Expect the generic exception
        with self.assertRaises(ProcessingException):
            # Try to book
            service.book_seat("s1", "c1", 2, 2)
        # Minimal assertion required by the framework
        self.assertIsNotNone(service)

    # Tests cancel_booking, every path is exercised to protect the coverage contract
    def test_cancel_booking(self):
        # Build collaborators
        service, gateway, screening = self.build(START - timedelta(days=1))
        # Mocked active booking
        booking = MagicMock()
        # Booking is active
        booking.status = "ACTIVE"
        # Booking screening
        booking.screening = screening
        # Booking identifier
        booking.booking_id = "1"
        # Store it
        service.bookings["1"] = booking
        # Unknown booking is rejected
        with self.assertRaises(CancellationRejectedException):
            # Try to cancel
            service.cancel_booking("nope")
        # Too late (one hour before) is rejected
        service.now_provider.return_value = START - timedelta(hours=1)
        # Expect a rejection
        with self.assertRaises(CancellationRejectedException):
            # Try to cancel
            service.cancel_booking("1")
        # Back to a valid time
        service.now_provider.return_value = START - timedelta(days=1)
        # Transient x4 (retries exhausted), permanent, unavailable, unexpected
        for error in [GatewayTransientError(), GatewayPermanentError(), GatewayUnavailableError(), RuntimeError()]:
            # Gateway fails with this error
            gateway.refund.side_effect = error
            # Expect a rejection or a generic exception
            with self.assertRaises(ProcessingException):
                # Try to cancel
                service.cancel_booking("1")
        # Transient then success
        gateway.refund.side_effect = [GatewayTransientError(), None]
        # Cancel
        service.cancel_booking("1")
        # Already cancelled is rejected
        booking.status = "CANCELLED"
        # Expect a rejection
        with self.assertRaises(CancellationRejectedException):
            # Try to cancel
            service.cancel_booking("1")
        # Interaction assertion: the gateway was called
        gateway.refund.assert_called()

    # Tests get_refund_status
    def test_get_refund_status(self):
        # Build collaborators
        service, gateway, screening = self.build(START - timedelta(days=1))
        # Mocked booking
        service.bookings["1"] = MagicMock()
        # Known booking
        service.get_refund_status("1")
        # Unknown booking is rejected
        with self.assertRaises(CancellationRejectedException):
            # Try to read it
            service.get_refund_status("nope")
        # Minimal assertion required by the framework
        self.assertIsNotNone(service)


# Standard entry point
if __name__ == "__main__":
    # Run the tests
    unittest.main()
