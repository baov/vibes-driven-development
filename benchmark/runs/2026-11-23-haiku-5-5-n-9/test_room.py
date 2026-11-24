# Import unittest to structure the test cases
import unittest
# Import patch to replace the module logger with a mock
from unittest.mock import patch

# Import the class under test and the generic exception it raises
from seat_booking import ProcessingException, Room


# Test case mirroring the Room class
class RoomTest(unittest.TestCase):
    # Verify that a room without rows or seats is rejected and logged
    @patch("seat_booking.logger")
    def test___post_init__(self, logger):
        # Expect the construction of a room with no rows to fail
        with self.assertRaises(ProcessingException):
            # Build a room with zero rows
            Room(rows=0, seats_per_row=3)
        # Assert the invalid dimensions were logged
        logger.error.assert_called_once()

    # Verify that the seats of the room are listed for every row and number
    def test_seats(self):
        # Ask a room of two rows and three seats per row for its seats
        seats = Room(rows=2, seats_per_row=3).seats()
        # Assert that all six seats were listed
        self.assertEqual(len(seats), 6)
