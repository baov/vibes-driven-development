# Standard library test framework
import unittest

# Class under test
from seat_booking import GatewayPermanentError


# Mirror test of GatewayPermanentError
class GatewayPermanentErrorTest(unittest.TestCase):
    # Tests GatewayPermanentError
    def test_gateway_permanent_error(self):
        # Build the object
        data = GatewayPermanentError('x')
        # Minimal assertion required by the framework
        self.assertIsNotNone(data)
