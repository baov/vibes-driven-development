# Mirror test for ProcessingException and the gateway error types.
import unittest
from seat_booking import (ProcessingException, TransientGatewayError,
                          PermanentGatewayError, GatewayUnavailableError)


class ProcessingExceptionTest(unittest.TestCase):
    def test_init(self):
        self.assertEqual(ProcessingException("m", "r").reason, "r")

    def test_gateway_errors(self):
        self.assertTrue(all(issubclass(e, Exception) for e in
                            (TransientGatewayError, PermanentGatewayError, GatewayUnavailableError)))
