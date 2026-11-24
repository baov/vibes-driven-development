# Tests for PaymentGateway, mirroring seat_booking/payment_gateway.py.
import unittest

# Import the gateway contract under test.
from seat_booking.payment_gateway import PaymentGateway


# Test class mirroring PaymentGateway; one test per method.
class PaymentGatewayTest(unittest.TestCase):
    # Check that the base gateway refuses to refund.
    def test_refund(self):
        # Build the base gateway, which has no provider behind it.
        gateway = PaymentGateway()
        # Expect the unimplemented refund to raise.
        with self.assertRaises(NotImplementedError):
            # Call refund on the base gateway.
            gateway.refund("1", 1200)
