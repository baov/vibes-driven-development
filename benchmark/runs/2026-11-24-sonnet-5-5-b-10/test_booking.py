# Standard library test framework
import unittest

# Class under test
from seat_booking import Booking


# Mirror test of Booking
class BookingTest(unittest.TestCase):
    # Tests Booking
    def test_booking(self):
        # Build the object
        data = Booking('1', None, 'c', 1, 1)
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
