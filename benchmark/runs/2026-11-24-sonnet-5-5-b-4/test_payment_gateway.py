# Unit test framework.
import unittest

# Class under test.
from seat_booking import PaymentGateway


# Mirror test of PaymentGateway.
class PaymentGatewayTest(unittest.TestCase):
    # Test of refund: the base contract is abstract.
    def test_refund(self):
        # The base class refuses to refund.
        with self.assertRaises(NotImplementedError):
            PaymentGateway().refund("B1", 10.0)
