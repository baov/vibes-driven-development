# Unit test framework.
import unittest
# Mocks for collaborators.
from unittest.mock import MagicMock

# Class under test and constants.
from seat_booking import Booking, BOOKING_ACTIVE, REFUND_NOT_REQUESTED


# Mirror test of Booking.
class BookingTest(unittest.TestCase):
    # Test of the constructor.
    def test_init(self):
        # Mocked screening.
        screening = MagicMock()
        # Build the booking.
        result = Booking("B1", "c1", screening, 2, 3)
        # Check the fields and initial states.
        self.assertEqual(("B1", "c1", screening, 2, 3, BOOKING_ACTIVE, REFUND_NOT_REQUESTED),
                         (result.booking_id, result.client_id, result.screening, result.row,
                          result.seat, result.status, result.refund_status))
