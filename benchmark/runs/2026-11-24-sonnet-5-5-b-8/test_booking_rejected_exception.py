"""Mirror test of seat_booking.BookingRejectedException."""
# Import the unittest framework.
import unittest

# Import the class under test.
from seat_booking import BookingRejectedException


# Tests of BookingRejectedException.
class BookingRejectedExceptionTest(unittest.TestCase):

    # __init__ keeps the reason.
    def test___init__(self):
        # The reason is exposed.
        self.assertEqual(BookingRejectedException("why").reason, "why")
