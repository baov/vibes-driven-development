# Standard unittest framework
import unittest

# Class under test
from seat_booking import ProcessingException


# One test class per production class
class ProcessingExceptionTest(unittest.TestCase):
    # One test per method (the constructor)
    def test_init(self):
        # Build the exception
        info = ProcessingException("reason")
        # Single assertion
        self.assertIsNotNone(info.reason)
