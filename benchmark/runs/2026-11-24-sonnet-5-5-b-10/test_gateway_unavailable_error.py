# Standard library test framework
import unittest

# Class under test
from seat_booking import GatewayUnavailableError


# Mirror test of GatewayUnavailableError
class GatewayUnavailableErrorTest(unittest.TestCase):
    # Tests GatewayUnavailableError
    def test_gateway_unavailable_error(self):
        # Build the object
        data = GatewayUnavailableError('x')
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
