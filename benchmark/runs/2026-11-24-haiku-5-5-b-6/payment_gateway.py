# Module logger; records the unimplemented-refund failure before it is raised.
import logging

# Logger for this module.
logger = logging.getLogger(__name__)


# Raised by a gateway refund that failed but may succeed if retried.
class TransientPaymentError(Exception):
    pass


# Raised by a gateway refund that failed and must not be retried.
class PermanentPaymentError(Exception):
    pass


# Raised when the gateway cannot be reached or is down.
class PaymentGatewayUnavailableError(Exception):
    pass


# Contract for the payment gateway that BookingManager refunds through.
class PaymentGateway:
    # Refund an amount in integer cents for a booking; concrete gateways override this.
    def refund(self, booking_id, amount_cents):
        # Record that the base contract was called without an implementation.
        logger.error("PaymentGateway.refund is not implemented for booking %s", booking_id)
        # Signal that a concrete gateway must provide refund.
        raise NotImplementedError
