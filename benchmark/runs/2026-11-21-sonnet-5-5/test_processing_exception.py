# unittest is the standard-library test framework
import unittest

# Classes under test
from seat_booking import ProcessingException, SeatAlreadyBookedException


# One test class for the exception hierarchy
class ProcessingExceptionTest(unittest.TestCase):
    # The booking rejection is catchable as the generic exception
    def test_processing_exception(self):
        # Subclass relationship holds
        self.assertTrue(issubclass(SeatAlreadyBookedException, ProcessingException))
