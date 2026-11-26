# Import unittest to structure the test case
import unittest
# Import datetime to build a start time for the screening
from datetime import datetime

# Import the class under test and the data it is built from
from seat_booking import BookingData, RoomData, ScreeningData


class TestBookingData(unittest.TestCase):
    # Verify a booking keeps the status it was built with
    def test_construct(self):
        # Create a booking for seat 0 of row 0 of a screening
        booking = BookingData(
            booking_id="b1",
            screening=ScreeningData("s1", datetime(2030, 1, 1, 18, 0), RoomData(5, 10), 12.5),
            row=0,
            seat=0,
            client_id="client",
            status="active",
            refund_status="none",
        )
        # Check that the status was stored
        self.assertEqual(booking.status, "active")
