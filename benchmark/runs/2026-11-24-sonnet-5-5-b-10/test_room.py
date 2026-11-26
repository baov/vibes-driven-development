# Standard library test framework
import unittest

# Class under test
from seat_booking import Room


# Mirror test of Room
class RoomTest(unittest.TestCase):
    # Tests Room
    def test_room(self):
        # Build the object
        data = Room(2, 2)
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
