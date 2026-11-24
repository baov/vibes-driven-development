# Import the standard test framework
import unittest
# Import datetime helpers for the fixed screening start and the controlled clock
from datetime import datetime, timedelta, timezone
# Import Mock and patch to replace collaborators with test doubles
from unittest.mock import Mock, patch

# Import the class under test and the types its assertions refer to
from seat_booking import (
    BookingManager,
    BookingStatus,
    GatewayUnavailableException,
    PermanentGatewayException,
    ProcessingException,
    RefundStatus,
    TransientGatewayException,
)


# Mirror test suite for BookingManager: one test per public method, every collaborator mocked
class BookingManagerTest(unittest.TestCase):
    # Prepare the mocked screening and logger shared by every test
    def setUp(self):
        # Fixed start time of the mocked screening
        self.start_time = datetime(2027, 1, 1, 20, 0, tzinfo=timezone.utc)
        # Mocked screening with a 5-row room of 10 seats and a price of 1200 cents
        self.screening = Mock(screening_id="s1", start_time=self.start_time, price_cents=1200)
        # Mocked room giving the seat grid of the screening
        self.screening.room = Mock(rows=5, seats_per_row=10)
        # Create a patcher that replaces the module logger with a mock
        logger_patcher = patch("seat_booking.logger")
        # Start the logger patch so logging calls go to the mock
        logger_patcher.start()
        # Undo the logger patch after each test
        self.addCleanup(logger_patcher.stop)

    # Build a manager with a mocked gateway and clock, holding one booking of row 1 seat 1
    def _manager_with_booking(self, now, refund_effect=None):
        # Create a gateway mock for the refund calls
        gateway = Mock()
        # Script the outcome of each refund call
        gateway.refund.side_effect = refund_effect
        # Create a clock mock that reports the requested current time
        clock = Mock(return_value=now)
        # Create the manager under test with the mocked collaborators
        manager = BookingManager(gateway, clock)
        # Register the mocked screening with the manager
        manager.add_screening(self.screening)
        # Book row 1 seat 1 so that a cancellation has a booking to act on
        booking = manager.book_seat("s1", 1, 1)
        # Return the manager, the gateway mock and the booking
        return manager, gateway, booking

    # Check that a registered screening accepts bookings
    def test_add_screening(self):
        # Create a manager with mocked gateway and clock
        manager = BookingManager(Mock(), Mock())
        # Register the mocked screening
        manager.add_screening(self.screening)
        # Book a seat in it to confirm the screening was registered
        booking = manager.book_seat("s1", 1, 1)
        # Check that the booking belongs to the registered screening
        self.assertEqual(booking.screening_id, "s1")

    # Cover the success path and every rejection path of book_seat
    def test_book_seat(self):
        # Create a manager with mocked gateway and clock
        manager = BookingManager(Mock(), Mock())
        # Register the mocked screening
        manager.add_screening(self.screening)
        # Check that a free, valid seat is booked as active
        with self.subTest("free seat is booked"):
            # Book row 2 seat 3 for the screening
            booking = manager.book_seat("s1", 2, 3)
            # Check that the new booking is active
            self.assertIs(booking.status, BookingStatus.ACTIVE)
        # Check that bookings for unknown screenings are rejected
        with self.subTest("unknown screening rejected"):
            # Booking an unknown screening must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt the booking against a screening that was never registered
                manager.book_seat("unknown", 1, 1)
        # Check that seats outside the room are rejected
        for row, seat_number in [(0, 1), (6, 1), (1, 0), (1, 11)]:
            # Run the check for each invalid seat coordinate
            with self.subTest(row=row, seat_number=seat_number):
                # Booking an invalid seat must raise the generic exception
                with self.assertRaises(ProcessingException):
                    # Attempt the booking of the invalid seat
                    manager.book_seat("s1", row, seat_number)
        # Check that a seat already held by an active booking is rejected
        with self.subTest("double booking rejected"):
            # Booking the same seat twice must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt to book row 2 seat 3 again
                manager.book_seat("s1", 2, 3)

    # Cover the success path and every rejection and refund-failure path of cancel_booking
    def test_cancel_booking(self):
        # Check that a cancellation made three hours ahead refunds the seat
        with self.subTest("refund succeeds"):
            # Build a booking with the clock three hours before the start
            manager, gateway, booking = self._manager_with_booking(self.start_time - timedelta(hours=3))
            # Cancel the booking
            cancelled = manager.cancel_booking(booking.booking_id)
            # Check that the booking is now cancelled
            self.assertIs(cancelled.status, BookingStatus.CANCELLED)
            # Check that the gateway was asked to refund the price paid
            gateway.refund.assert_called_once_with(booking.booking_id, 1200)
        # Check that a cancellation exactly two hours ahead is still allowed
        with self.subTest("exactly at the cutoff is allowed"):
            # Build a booking with the clock exactly two hours before the start
            manager, gateway, booking = self._manager_with_booking(self.start_time - timedelta(hours=2))
            # Cancel the booking
            cancelled = manager.cancel_booking(booking.booking_id)
            # Check that the booking is now cancelled
            self.assertIs(cancelled.status, BookingStatus.CANCELLED)
        # Check that unknown bookings are rejected
        with self.subTest("unknown booking rejected"):
            # Build a manager whose clock is far before the start
            manager, _, _ = self._manager_with_booking(self.start_time - timedelta(hours=3))
            # Cancelling an unknown booking must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt to cancel a booking identifier that does not exist
                manager.cancel_booking(999)
        # Check that cancelling twice is rejected
        with self.subTest("already cancelled rejected"):
            # Build a booking and cancel it once
            manager, _, booking = self._manager_with_booking(self.start_time - timedelta(hours=3))
            # Cancel the booking the first time
            manager.cancel_booking(booking.booking_id)
            # The second cancellation must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt to cancel the same booking again
                manager.cancel_booking(booking.booking_id)
        # Check that a cancellation less than two hours ahead is rejected
        with self.subTest("too late rejected"):
            # Build a booking with the clock one hour before the start
            manager, gateway, booking = self._manager_with_booking(self.start_time - timedelta(hours=1))
            # The late cancellation must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt the late cancellation
                manager.cancel_booking(booking.booking_id)
            # Check that no refund was requested for the rejected cancellation
            gateway.refund.assert_not_called()
        # Check that transient failures are retried and then succeed
        with self.subTest("transient failures retried then succeed"):
            # Build a booking whose refund fails twice transiently and then succeeds
            manager, gateway, booking = self._manager_with_booking(
                self.start_time - timedelta(hours=3),
                [TransientGatewayException(), TransientGatewayException(), None],
            )
            # Cancel the booking
            cancelled = manager.cancel_booking(booking.booking_id)
            # Check that the booking was cancelled after the retries
            self.assertIs(cancelled.status, BookingStatus.CANCELLED)
        # Check that transient failures beyond the retry limit reject the cancellation
        with self.subTest("transient failures exhausted rejected"):
            # Build a booking whose refund always fails transiently
            manager, gateway, booking = self._manager_with_booking(
                self.start_time - timedelta(hours=3),
                [TransientGatewayException() for _ in range(4)],
            )
            # Exhausting the retries must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation whose refund keeps failing
                manager.cancel_booking(booking.booking_id)
            # Check that the refund was attempted once plus three retries
            self.assertEqual(gateway.refund.call_count, 4)
        # Check that a permanent refund failure keeps the booking active
        with self.subTest("permanent failure keeps booking active"):
            # Build a booking whose refund is refused permanently
            manager, _, booking = self._manager_with_booking(
                self.start_time - timedelta(hours=3),
                PermanentGatewayException(),
            )
            # Cancel the booking, which returns it without raising
            result = manager.cancel_booking(booking.booking_id)
            # Check that the returned booking is still active
            self.assertIs(result.status, BookingStatus.ACTIVE)
        # Check that an unavailable gateway rejects the cancellation
        with self.subTest("gateway unavailable rejected"):
            # Build a booking whose gateway reports it is unavailable
            manager, _, booking = self._manager_with_booking(
                self.start_time - timedelta(hours=3),
                GatewayUnavailableException(),
            )
            # The unavailable gateway must make the cancellation raise the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation while the gateway is down
                manager.cancel_booking(booking.booking_id)
        # Check that an unexpected gateway error rejects the cancellation
        with self.subTest("unexpected gateway error rejected"):
            # Build a booking whose gateway raises an unknown error
            manager, _, booking = self._manager_with_booking(
                self.start_time - timedelta(hours=3),
                RuntimeError("boom"),
            )
            # The unknown error must surface as the generic exception
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation against the failing gateway
                manager.cancel_booking(booking.booking_id)

    # Cover the unknown-booking rejection and each refund status a booking can expose
    def test_get_refund_status(self):
        # Check that an unknown booking is rejected
        with self.subTest("unknown booking rejected"):
            # Build a manager with a booking that is not the one requested
            manager, _, _ = self._manager_with_booking(self.start_time - timedelta(hours=3))
            # Looking up an unknown booking must raise the generic exception
            with self.assertRaises(ProcessingException):
                # Request the refund status of a booking identifier that does not exist
                manager.get_refund_status(999)
        # Check that a booking that was never cancelled has no refund requested
        with self.subTest("not requested before cancellation"):
            # Build a manager with a booking that has not been cancelled
            manager, _, booking = self._manager_with_booking(self.start_time - timedelta(hours=3))
            # Check that the refund status is not requested
            self.assertIs(manager.get_refund_status(booking.booking_id), RefundStatus.NOT_REQUESTED)
        # Check that a confirmed refund is exposed as refunded
        with self.subTest("refunded after cancellation"):
            # Build a manager and cancel its booking so the refund succeeds
            manager, _, booking = self._manager_with_booking(self.start_time - timedelta(hours=3))
            # Cancel the booking
            manager.cancel_booking(booking.booking_id)
            # Check that the refund status is refunded
            self.assertIs(manager.get_refund_status(booking.booking_id), RefundStatus.REFUNDED)
        # Check that a permanently refused refund is exposed as failed
        with self.subTest("failed after permanent refusal"):
            # Build a manager whose refund is refused permanently
            manager, _, booking = self._manager_with_booking(
                self.start_time - timedelta(hours=3),
                PermanentGatewayException(),
            )
            # Cancel the booking, which keeps it active with a failed refund
            manager.cancel_booking(booking.booking_id)
            # Check that the refund status is failed
            self.assertIs(manager.get_refund_status(booking.booking_id), RefundStatus.FAILED)
