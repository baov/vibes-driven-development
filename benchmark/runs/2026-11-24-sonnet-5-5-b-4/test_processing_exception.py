# Unit test framework.
import unittest

# Class under test.
from seat_booking import ProcessingException


# Mirror test of ProcessingException.
class ProcessingExceptionTest(unittest.TestCase):
    # Test of the constructor.
    def test_init(self):
        # Build the exception.
        result = ProcessingException("msg", "R")
        # Check message and reason.
        self.assertEqual(("msg", "R"), (str(result), result.reason))
