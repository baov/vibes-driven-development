"""Mirror test of seat_booking.PaymentGatewayHandler."""
# Import the unittest framework.
import unittest

# Import the class under test.
from seat_booking import PaymentGatewayHandler


# Tests of PaymentGatewayHandler.
class PaymentGatewayHandlerTest(unittest.TestCase):

    # refund must be implemented by concrete gateways.
    def test_refund(self):
        # The abstract method raises.
        with self.assertRaises(NotImplementedError):
            # Call it.
            PaymentGatewayHandler().refund("B1", 100)
