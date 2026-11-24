# Standard library test framework
import unittest

# Class under test
from seat_booking import GatewayTransientError


# Mirror test of GatewayTransientError
class GatewayTransientErrorTest(unittest.TestCase):
    # Tests GatewayTransientError
    def test_gateway_transient_error(self):
        # Build the object
        data = GatewayTransientError('x')
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
