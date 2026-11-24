# Import unittest to structure the test case
import unittest

# Import the class under test from the package
from seat_booking import ProcessingException


class TestProcessingException(unittest.TestCase):
    # Verify the generic exception carries the message it was raised with
    def test_construct(self):
        # Create the exception with a message
        error = ProcessingException("rejected")
        # Check that the message is preserved
        self.assertEqual(str(error), "rejected")
