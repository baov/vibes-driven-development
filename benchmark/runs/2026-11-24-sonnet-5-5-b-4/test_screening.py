# Unit test framework.
import unittest
# Mocks for collaborators.
from unittest.mock import MagicMock

# Class under test.
from seat_booking import Screening


# Mirror test of Screening.
class ScreeningTest(unittest.TestCase):
    # Test of the constructor.
    def test_init(self):
        # Mocked room and start time.
        room = MagicMock()
        start = MagicMock()
        # Build the screening.
        result = Screening("S1", start, room, 12.5)
        # Check the fields.
        self.assertEqual(("S1", start, room, 12.5),
                         (result.screening_id, result.start_time, result.room, result.price))
