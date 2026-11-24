# Import unittest to structure the test case
import unittest
# Import datetime and timedelta to build screening times around the cancellation cut-off
from datetime import datetime, timedelta
# Import ANY, Mock and patch to replace collaborators with test doubles
from unittest.mock import ANY, Mock, patch

# Import the class under test and the collaborators and constants it relies on
from seat_booking import (
    CANCELLATION_WINDOW,
    MAX_REFUND_RETRIES,
    BookingManager,
    PaymentGatewayException,
    ProcessingException,
)

# Fixed start time of the screening used by every test
START = datetime(2030, 1, 1, 18, 0)
# Latest moment at which a cancellation is still accepted
NOW_OK = START - CANCELLATION_WINDOW


# Build a screening double whose room has the given layout
def make_screening(rows=5, seats_per_row=10, price=12.5):
    # Create the screening double with an identifier, start time and price
    screening = Mock(screening_id="s1", start_time=START, price=price)
    # Attach a room double with the given number of rows and seats per row
    screening.room = Mock(rows=rows, seats_per_row=seats_per_row)
    # Return the screening double
    return screening


# Build a manager that already holds one active booking for seat 0 of row 0
def make_booked_manager(gateway):
    # Create the manager under test with the gateway double
    manager = BookingManager(gateway)
    # Create the screening double the seat is booked for
    screening = make_screening()
    # Create the booking double that the patched booking data class will return
    booking = Mock(booking_id="b1", row=0, seat=0, status="active", refund_status="none", screening=screening)
    # Replace the booking data class so that book_seat stores this double
    with patch("seat_booking.BookingData", return_value=booking):
        # Book seat 0 of row 0 for a client
        manager.book_seat(screening, 0, 0, "client")
    # Return the manager and the booking double for the test to inspect
    return manager, booking


class TestBookingManager(unittest.TestCase):
    # Verify the manager can be constructed with a gateway
    def test___init__(self):
        # Create the manager with a gateway double
        manager = BookingManager(Mock())
        # Check that the manager was created
        self.assertIsInstance(manager, BookingManager)

    # Verify book_seat rejects invalid or taken seats and registers valid ones
    def test_book_seat(self):
        # Check that a row beyond the room layout is rejected
        with self.subTest("row outside room"):
            # Create a manager with a gateway double
            manager = BookingManager(Mock())
            # Expect the out-of-range booking to be rejected
            with self.assertRaises(ProcessingException):
                # Book row 5 of a room that only has five rows
                manager.book_seat(make_screening(), 5, 0, "client")
        # Check that a seat beyond the seats of a row is rejected
        with self.subTest("seat outside room"):
            # Create a manager with a gateway double
            manager = BookingManager(Mock())
            # Expect the out-of-range booking to be rejected
            with self.assertRaises(ProcessingException):
                # Book seat 10 of a row that only has ten seats
                manager.book_seat(make_screening(), 0, 10, "client")
        # Check that a seat already held by an active booking is rejected
        with self.subTest("already booked"):
            # Create a manager with a gateway double
            manager = BookingManager(Mock())
            # Create the screening double the seat belongs to
            screening = make_screening()
            # Replace the booking data class so that the first booking succeeds
            with patch("seat_booking.BookingData"):
                # Book seat 0 of row 0 for the first client
                manager.book_seat(screening, 0, 0, "client")
                # Expect a second booking of the same seat to be rejected
                with self.assertRaises(ProcessingException):
                    # Try to book the same seat for another client
                    manager.book_seat(screening, 0, 0, "other")
        # Check that a valid seat is booked with an active status and no refund yet
        with self.subTest("booked"):
            # Create a manager with a gateway double
            manager = BookingManager(Mock())
            # Create the screening double the seat belongs to
            screening = make_screening()
            # Replace the booking data class so that its construction can be inspected
            with patch("seat_booking.BookingData") as booking_data:
                # Book seat 0 of row 0 for a client
                manager.book_seat(screening, 0, 0, "client")
            # Verify the booking data was built with the expected fields
            booking_data.assert_called_once_with(
                booking_id=ANY,
                screening=screening,
                row=0,
                seat=0,
                client_id="client",
                status="active",
                refund_status="none",
            )

    # Verify cancel_booking enforces the rules and refunds through the gateway
    def test_cancel_booking(self):
        # Check that an unknown booking cannot be cancelled
        with self.subTest("unknown booking"):
            # Create a manager that holds one booking, which is not the one cancelled
            manager, _ = make_booked_manager(Mock())
            # Expect the cancellation of an unknown identifier to be rejected
            with self.assertRaises(ProcessingException):
                # Cancel a booking identifier that does not exist
                manager.cancel_booking("missing", NOW_OK)
        # Check that an already cancelled booking cannot be cancelled again
        with self.subTest("already cancelled"):
            # Create the gateway double and a manager holding one booking
            gateway = Mock()
            manager, booking = make_booked_manager(gateway)
            # Mark the booking as already cancelled
            booking.status = "cancelled"
            # Expect the second cancellation to be rejected
            with self.assertRaises(ProcessingException):
                # Cancel the booking that is already cancelled
                manager.cancel_booking("b1", NOW_OK)
        # Check that a cancellation later than the cut-off is rejected without refunding
        with self.subTest("inside cancellation window"):
            # Create the gateway double and a manager holding one booking
            gateway = Mock()
            manager, _ = make_booked_manager(gateway)
            # Expect the late cancellation to be rejected
            with self.assertRaises(ProcessingException):
                # Cancel one second after the cut-off
                manager.cancel_booking("b1", NOW_OK + timedelta(seconds=1))
            # Verify the gateway was never asked to refund
            gateway.refund.assert_not_called()
        # Check that a cancellation on time refunds the seat price once
        with self.subTest("refunded on time"):
            # Create the gateway double and a manager holding one booking
            gateway = Mock()
            manager, _ = make_booked_manager(gateway)
            # Cancel exactly at the cut-off
            manager.cancel_booking("b1", NOW_OK)
            # Verify the gateway was asked to refund the seat price once
            gateway.refund.assert_called_once_with("b1", 12.5)
        # Check that a transient gateway failure is retried and then succeeds
        with self.subTest("transient failure then success"):
            # Create a gateway that fails transiently once and then succeeds
            gateway = Mock()
            gateway.refund.side_effect = [PaymentGatewayException("transient"), None]
            # Create a manager holding one booking
            manager, _ = make_booked_manager(gateway)
            # Cancel the booking on time
            manager.cancel_booking("b1", NOW_OK)
            # Verify the gateway was called again after the transient failure
            self.assertEqual(gateway.refund.call_count, 2)
        # Check that transient failures are retried up to the limit and then rejected
        with self.subTest("transient failures exhausted"):
            # Create a gateway that always fails transiently
            gateway = Mock()
            gateway.refund.side_effect = [PaymentGatewayException("transient")] * (MAX_REFUND_RETRIES + 1)
            # Create a manager holding one booking
            manager, _ = make_booked_manager(gateway)
            # Expect the cancellation to be rejected once the retries are used up
            with self.assertRaises(ProcessingException):
                # Cancel the booking on time
                manager.cancel_booking("b1", NOW_OK)
            # Verify the first attempt plus every retry was made
            self.assertEqual(gateway.refund.call_count, MAX_REFUND_RETRIES + 1)
        # Check that a permanent gateway failure rejects the cancellation without retrying
        with self.subTest("permanent failure"):
            # Create a gateway that fails permanently
            gateway = Mock()
            gateway.refund.side_effect = PaymentGatewayException("permanent")
            # Create a manager holding one booking
            manager, _ = make_booked_manager(gateway)
            # Expect the cancellation to be rejected
            with self.assertRaises(ProcessingException):
                # Cancel the booking on time
                manager.cancel_booking("b1", NOW_OK)
            # Verify the gateway was called only once
            self.assertEqual(gateway.refund.call_count, 1)
        # Check that an unavailable gateway rejects the cancellation without retrying
        with self.subTest("gateway unavailable"):
            # Create a gateway that is unavailable
            gateway = Mock()
            gateway.refund.side_effect = PaymentGatewayException("unavailable")
            # Create a manager holding one booking
            manager, _ = make_booked_manager(gateway)
            # Expect the cancellation to be rejected
            with self.assertRaises(ProcessingException):
                # Cancel the booking on time
                manager.cancel_booking("b1", NOW_OK)
            # Verify the gateway was called only once
            self.assertEqual(gateway.refund.call_count, 1)

    # Verify get_refund_status reports the refund outcome of a booking
    def test_get_refund_status(self):
        # Check that an unknown booking has no refund status to report
        with self.subTest("unknown booking"):
            # Create a manager with a gateway double and no bookings
            manager = BookingManager(Mock())
            # Expect the query for an unknown identifier to be rejected
            with self.assertRaises(ProcessingException):
                # Query a booking identifier that does not exist
                manager.get_refund_status("missing")
        # Check that a booking with no refund attempt reports none
        with self.subTest("no refund attempted"):
            # Create a manager holding one booking
            manager, _ = make_booked_manager(Mock())
            # Verify the refund status is none
            self.assertEqual(manager.get_refund_status("b1"), "none")
        # Check that a rejected refund is reported as failed while the booking stays active
        with self.subTest("refund failed"):
            # Create a gateway that fails permanently
            gateway = Mock()
            gateway.refund.side_effect = PaymentGatewayException("permanent")
            # Create a manager holding one booking
            manager, _ = make_booked_manager(gateway)
            # Expect the cancellation to be rejected after the failed refund
            with self.assertRaises(ProcessingException):
                # Cancel the booking on time
                manager.cancel_booking("b1", NOW_OK)
            # Verify the refund status is failed
            self.assertEqual(manager.get_refund_status("b1"), "failed")
        # Check that a completed refund is reported as refunded
        with self.subTest("refunded"):
            # Create a manager holding one booking with a gateway that succeeds
            manager, _ = make_booked_manager(Mock())
            # Cancel the booking on time
            manager.cancel_booking("b1", NOW_OK)
            # Verify the refund status is refunded
            self.assertEqual(manager.get_refund_status("b1"), "refunded")
