# Import unittest to structure the test case
import unittest

# Import the class under test from the package
from seat_booking import RoomData


class TestRoomData(unittest.TestCase):
    # Verify a room keeps the number of rows it was built with
    def test_construct(self):
        # Create a room with five rows of ten seats
        room = RoomData(rows=5, seats_per_row=10)
        # Check that the row count was stored
        self.assertEqual(room.rows, 5)
