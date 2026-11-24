# Mirror test for Booking: constructor only.
import unittest
from unittest import mock
from seat_booking import Booking


class BookingTest(unittest.TestCase):
    def test_init(self):
        self.assertFalse(Booking(1, "c", mock.Mock(), 1, 1).cancelled)
