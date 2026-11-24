# Import the standard library test framework used for every test in this repository
import unittest
# Import the mock library used to replace every collaborator of the class under test
from unittest.mock import Mock
# Import datetime for screening start times and timedelta for the cancellation deadline
from datetime import datetime, timedelta
# Import the logging module so the expected exception logs can be silenced during tests
import logging
# Import the production classes and exceptions under test from the package
from seat_booking import BookingManager, BookingRejectedError, PaymentGatewayPermanentError, PaymentGatewayTransientError, PaymentGatewayUnavailableError, ProcessingException

# Silence the error logs that the service writes on purpose while exercising failure paths
logging.disable(logging.CRITICAL)


# Test class mirroring the BookingManager class in the seat_booking package
class BookingManagerTest(unittest.TestCase):

    # Prepare the collaborators shared by every test in this class
    def setUp(self):
        # Mock the payment gateway, the only collaborator passed into the manager
        self.gateway = Mock()
        # Create the manager under test with the mocked gateway
        self.manager = BookingManager(self.gateway)
        # Mock a screening carrying a fixed start time, price and identifier
        self.screening = Mock(screening_id="S1", start_time=datetime(2030, 1, 1, 20, 0), price_cents=1200)
        # Mock the room layout of the screening as two rows of three seats
        self.screening.room = Mock(rows=2, seats_per_row=3)

    # Test that booking creates an active seat, rejects a held seat and rejects a seat outside the room
    def test_book_seat(self):
        # Book a valid seat on the screening
        booking = self.manager.book_seat(self.screening, 1, 2, "client-1")
        # Check the new booking is active
        self.assertEqual(booking.status, "active")
        # Group the rejection of a seat already held
        with self.subTest("already booked"):
            # Expect a rejection when the same seat is booked again
            with self.assertRaises(BookingRejectedError):
                # Attempt to book the seat that is already held
                self.manager.book_seat(self.screening, 1, 2, "client-2")
        # Group the rejection of a seat outside the room layout
        with self.subTest("outside room layout"):
            # Expect a rejection when the row does not exist in the room
            with self.assertRaises(BookingRejectedError):
                # Attempt to book row 3 in a room with only two rows
                self.manager.book_seat(self.screening, 3, 1, "client-1")
        # Group the case where a cancelled booking releases its seat
        with self.subTest("seat free after cancellation"):
            # Cancel the first booking well before the screening starts
            self.manager.cancel_booking(booking.booking_id, datetime(2029, 12, 31, 12, 0))
            # Book the same seat again, which must succeed now that it is released
            rebooked = self.manager.book_seat(self.screening, 1, 2, "client-2")
            # Check the seat is held by the new booking
            self.assertEqual(rebooked.status, "active")

    # Test that cancellation refunds in every gateway outcome and rejects invalid cancellations
    def test_cancel_booking(self):
        # Build a fresh manager, gateway and booked seat for one scenario
        def setup_booking(refund_effect=None):
            # Mock a gateway whose refund behaves as configured for this scenario
            gateway = Mock(refund=Mock(side_effect=refund_effect))
            # Create a manager that uses the mocked gateway
            manager = BookingManager(gateway)
            # Book a seat so there is an active booking to cancel
            booking = manager.book_seat(self.screening, 1, 1, "client-1")
            # Return everything the scenario needs
            return manager, gateway, booking
        # Compute the latest moment a cancellation is still allowed
        deadline = self.screening.start_time - timedelta(hours=2)
        # Group the successful cancellation at the deadline
        with self.subTest("refunds at the deadline"):
            # Build a scenario where the gateway accepts the refund
            manager, gateway, booking = setup_booking()
            # Cancel the booking exactly two hours before the screening
            cancelled = manager.cancel_booking(booking.booking_id, deadline)
            # Check the refund is recorded as refunded
            self.assertEqual(cancelled.refund_status, "refunded")
        # Group the rejection of an unknown booking
        with self.subTest("unknown booking"):
            # Build a scenario with no booking under the id used below
            manager, _, _ = setup_booking()
            # Expect a rejection when cancelling an id that was never booked
            with self.assertRaises(BookingRejectedError):
                # Attempt to cancel a booking id that does not exist
                manager.cancel_booking("999", deadline)
        # Group the rejection of a repeated cancellation
        with self.subTest("already cancelled"):
            # Build a scenario and cancel its booking once
            manager, _, booking = setup_booking()
            # Cancel the booking the first time successfully
            manager.cancel_booking(booking.booking_id, deadline)
            # Expect a rejection when cancelling the same booking again
            with self.assertRaises(BookingRejectedError):
                # Attempt the second cancellation of the same booking
                manager.cancel_booking(booking.booking_id, deadline)
        # Group the rejection of a cancellation after the deadline
        with self.subTest("too late"):
            # Build a scenario with an active booking
            manager, _, booking = setup_booking()
            # Expect a rejection when cancelling one second after the deadline
            with self.assertRaises(BookingRejectedError):
                # Attempt the cancellation just after the two-hour window has closed
                manager.cancel_booking(booking.booking_id, deadline + timedelta(seconds=1))
        # Group the case where a transient failure is retried and then succeeds
        with self.subTest("transient failure then success"):
            # Build a scenario where the first refund fails transiently and the second succeeds
            manager, gateway, booking = setup_booking([PaymentGatewayTransientError(), None])
            # Cancel the booking, which triggers the retry
            cancelled = manager.cancel_booking(booking.booking_id, deadline)
            # Check the refund is recorded as refunded after the retry
            self.assertEqual(cancelled.refund_status, "refunded")
        # Group the case where transient failures exhaust every retry
        with self.subTest("transient failures exhaust retries"):
            # Build a scenario where every refund attempt fails transiently
            manager, gateway, booking = setup_booking([PaymentGatewayTransientError()] * 4)
            # Cancel the booking, which runs out of retries
            result = manager.cancel_booking(booking.booking_id, deadline)
            # Check the refund is recorded as failed
            self.assertEqual(result.refund_status, "failed")
        # Group the case where a permanent failure keeps the booking active
        with self.subTest("permanent failure keeps booking active"):
            # Build a scenario where the gateway refuses the refund permanently
            manager, gateway, booking = setup_booking(PaymentGatewayPermanentError())
            # Cancel the booking, which is refused by the gateway
            result = manager.cancel_booking(booking.booking_id, deadline)
            # Check the booking is still active after the refusal
            self.assertEqual(result.status, "active")
        # Group the case where an unavailable gateway rejects the cancellation
        with self.subTest("gateway unavailable rejects cancellation"):
            # Build a scenario where the gateway cannot process refunds
            manager, gateway, booking = setup_booking(PaymentGatewayUnavailableError())
            # Expect the cancellation to be rejected with a generic processing error
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation while the gateway is unavailable
                manager.cancel_booking(booking.booking_id, deadline)
        # Group the case where the gateway fails in an unexpected way
        with self.subTest("unexpected gateway failure"):
            # Build a scenario where the gateway raises an error the service does not expect
            manager, gateway, booking = setup_booking(RuntimeError("boom"))
            # Expect the failure to surface as a generic processing error
            with self.assertRaises(ProcessingException):
                # Attempt the cancellation while the gateway fails unexpectedly
                manager.cancel_booking(booking.booking_id, deadline)

    # Test that the refund status is reported per booking and rejects unknown bookings
    def test_get_refund_status(self):
        # Book a seat so there is a booking whose refund status can be read
        booking = self.manager.book_seat(self.screening, 2, 3, "client-1")
        # Group the status of a booking whose refund was never requested
        with self.subTest("not requested before cancellation"):
            # Check the status reads as not requested
            self.assertEqual(self.manager.get_refund_status(booking.booking_id), "not_requested")
        # Group the status of a booking after a successful refund
        with self.subTest("refunded after cancellation"):
            # Cancel the booking before the deadline so the refund succeeds
            self.manager.cancel_booking(booking.booking_id, datetime(2029, 12, 31, 12, 0))
            # Check the status reads as refunded
            self.assertEqual(self.manager.get_refund_status(booking.booking_id), "refunded")
        # Group the rejection of an unknown booking
        with self.subTest("unknown booking"):
            # Expect a rejection when asking for the status of a booking that does not exist
            with self.assertRaises(BookingRejectedError):
                # Attempt to read the status of an unknown booking id
                self.manager.get_refund_status("999")
