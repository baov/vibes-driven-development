# Import unittest to build the test cases of the Room class.
import unittest

# Import the class under test.
from seat_booking import Room


# Mirror test of the Room class: one test per method.
class RoomTest(unittest.TestCase):
    # Verifies that is_valid_seat accepts the first and last seat of the room.
    def test_is_valid_seat(self):
        # Build a room with 3 rows of 4 seats.
        room = Room(3, 4)
        # Check the corner seats are valid.
        self.assertTrue(room.is_valid_seat(1, 1) and room.is_valid_seat(3, 4))

    # Verifies that is_valid_seat rejects rows and seats outside the room.
    def test_is_valid_seat_rejects_out_of_range(self):
        # Build a room with 3 rows of 4 seats.
        room = Room(3, 4)
        # Check that a seat outside the room is not valid.
        self.assertFalse(room.is_valid_seat(0, 1) or room.is_valid_seat(4, 1) or room.is_valid_seat(1, 5))
