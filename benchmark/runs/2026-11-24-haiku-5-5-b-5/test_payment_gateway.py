# Standard library unittest framework used to run the test.
import unittest

# Class under test, imported from the production package.
from seat_booking import PaymentGateway


# Mirrors the PaymentGateway production class.
class PaymentGatewayTest(unittest.TestCase):
    # Tests the refund method, which must be implemented by subclasses.
    def test_refund(self):
        # Verify the base contract refuses to refund, so subclasses must provide it.
        with self.assertRaises(NotImplementedError):
            # Call the base implementation directly.
            PaymentGateway().refund("B1", 1200)
