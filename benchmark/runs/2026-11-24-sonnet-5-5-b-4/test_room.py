# Unit test framework.
import unittest

# Class under test.
from seat_booking import Room


# Mirror test of Room.
class RoomTest(unittest.TestCase):
    # Test of the constructor.
    def test_init(self):
        # Build the room.
        result = Room(5, 10)
        # Check the layout.
        self.assertEqual((5, 10), (result.rows, result.seats_per_row))
