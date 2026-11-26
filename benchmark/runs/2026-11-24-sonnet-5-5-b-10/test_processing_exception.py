# Standard library test framework
import unittest

# Class under test
from seat_booking import ProcessingException


# Mirror test of ProcessingException
class ProcessingExceptionTest(unittest.TestCase):
    # Tests ProcessingException
    def test_processing_exception(self):
        # Build the object
        data = ProcessingException('x')
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
