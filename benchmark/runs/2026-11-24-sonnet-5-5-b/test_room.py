# Mirror test for Room: one test per method.
import unittest
from seat_booking import Room


class RoomTest(unittest.TestCase):
    def test_has_seat(self):
        self.assertTrue(Room(2, 3).has_seat(1, 1))

    def test_has_seat2(self):
        self.assertFalse(Room(2, 3).has_seat(3, 1))
