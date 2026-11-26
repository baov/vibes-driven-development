# Standard library test framework
import unittest

# Class under test
from seat_booking import Screening


# Mirror test of Screening
class ScreeningTest(unittest.TestCase):
    # Tests Screening
    def test_screening(self):
        # Build the object
        data = Screening('s1', None, None, 1.0)
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
