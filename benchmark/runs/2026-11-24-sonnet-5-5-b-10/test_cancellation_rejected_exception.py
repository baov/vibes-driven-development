# Standard library test framework
import unittest

# Class under test
from seat_booking import CancellationRejectedException


# Mirror test of CancellationRejectedException
class CancellationRejectedExceptionTest(unittest.TestCase):
    # Tests CancellationRejectedException
    def test_cancellation_rejected_exception(self):
        # Build the object
        data = CancellationRejectedException('x')
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
