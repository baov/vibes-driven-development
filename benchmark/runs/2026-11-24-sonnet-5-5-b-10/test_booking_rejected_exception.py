# Standard library test framework
import unittest

# Class under test
from seat_booking import BookingRejectedException


# Mirror test of BookingRejectedException
class BookingRejectedExceptionTest(unittest.TestCase):
    # Tests BookingRejectedException
    def test_booking_rejected_exception(self):
        # Build the object
        data = BookingRejectedException('x')
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
