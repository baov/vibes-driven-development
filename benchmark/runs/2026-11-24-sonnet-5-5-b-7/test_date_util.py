# Standard unittest framework
import unittest
# Dates used as inputs
from datetime import datetime, timedelta

# Class under test
from seat_booking import DateUtil


# One test class per production class
class DateUtilTest(unittest.TestCase):
    # One test per method
    def test_is_at_least_hours_before(self):
        # Reference start time
        start = datetime(2026, 1, 1, 20, 0)
        # Call the method under test at exactly two hours before
        flag = DateUtil().is_at_least_hours_before(start - timedelta(hours=2), start, 2)
        # Single assertion
        self.assertIsNotNone(flag)
