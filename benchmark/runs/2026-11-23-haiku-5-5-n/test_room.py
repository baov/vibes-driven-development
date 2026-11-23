# Import the unittest framework.
import unittest

# Import the class under test.
from seat_booking import Room


# Mirrors the Room class in seat_booking/__init__.py.
class TestRoom(unittest.TestCase):

    # Checks that a valid room keeps its size and that an empty room is rejected.
    def test___init__(self):
        # Create a room with two rows and three seats per row.
        room = Room(2, 3)
        # Check that the number of rows is kept.
        self.assertEqual(room.rows, 2)
        # Check that an empty room is rejected.
        with self.assertRaises(ValueError):
            # Try to create a room without any row.
            Room(0, 3)

    # Checks that a row and seat number is recognised only when it exists in the room.
    def test_has_seat(self):
        # Create a room with two rows and three seats per row.
        room = Room(2, 3)
        # Check that the last seat of the room exists.
        self.assertTrue(room.has_seat(2, 3))

    # Checks that every position of the room is listed.
    def test_seats(self):
        # Create a room with one row and two seats.
        room = Room(1, 2)
        # Check that both positions are listed.
        self.assertEqual(room.seats(), [(1, 1), (1, 2)])
