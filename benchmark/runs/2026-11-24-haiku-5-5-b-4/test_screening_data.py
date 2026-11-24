# Import unittest to structure the test case
import unittest
# Import datetime to build a start time for the screening
from datetime import datetime

# Import the class under test from the package
from seat_booking import RoomData, ScreeningData


class TestScreeningData(unittest.TestCase):
    # Verify a screening keeps the price it was built with
    def test_construct(self):
        # Create a screening in a room with a price per seat
        screening = ScreeningData(
            screening_id="s1",
            start_time=datetime(2030, 1, 1, 18, 0),
            room=RoomData(rows=5, seats_per_row=10),
            price=12.5,
        )
        # Check that the price was stored
        self.assertEqual(screening.price, 12.5)
