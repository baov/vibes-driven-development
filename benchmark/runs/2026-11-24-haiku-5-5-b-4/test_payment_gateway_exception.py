# Import unittest to structure the test case
import unittest

# Import the class under test from the package
from seat_booking import PaymentGatewayException


class TestPaymentGatewayException(unittest.TestCase):
    # Verify the gateway exception keeps the kind of failure it was raised with
    def test___init__(self):
        # Create the exception for a transient failure
        error = PaymentGatewayException("transient")
        # Check that the kind of failure was stored
        self.assertEqual(error.kind, "transient")
