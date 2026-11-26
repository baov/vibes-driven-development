# Imports logging so the module's warnings and errors do not clutter test output
import logging
# Imports the time types used to build screenings and clock readings
from datetime import datetime, timedelta, timezone
# Imports the test case base class
import unittest
# Imports Mock to replace the payment gateway and the clock
from unittest.mock import Mock

# Imports the class under test and the types its tests use
from seat_booking import (
    NOT_REQUESTED,
    REFUNDED,
    GatewayPermanentError,
    GatewayTransientError,
    GatewayUnavailableError,
    ProcessingException,
    Screening,
    SeatBookingManager,
)

# Silences the module's logging during the tests
logging.disable(logging.CRITICAL)

# Fixes the start time of the screening used by the tests
SCREENING_START = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


# Holds one test per method of SeatBookingManager
class SeatBookingManagerTest(unittest.TestCase):
    # Checks that a manager can be built with a gateway and without a clock
    def test___init__(self):
        # Builds the manager with a mocked gateway and the default clock
        manager = SeatBookingManager(Mock())
        # Checks the manager was built
        self.assertIsNotNone(manager)

    # Checks that an added screening can be booked
    def test_add_screening(self):
        # Builds the manager with a mocked gateway
        manager = SeatBookingManager(Mock())
        # Registers a screening with two rows of three seats
        manager.add_screening(Screening(1, SCREENING_START, 2, 3, 1500))
        # Checks that a seat of the added screening can be booked
        self.assertEqual(manager.book_seat(1, 1, 1), 1)

    # Checks booking rules: unknown screening, seat outside the room and seat already booked
    def test_book_seat(self):
        # Builds the manager with a mocked gateway
        manager = SeatBookingManager(Mock())
        # Registers a screening with two rows of three seats
        manager.add_screening(Screening(1, SCREENING_START, 2, 3, 1500))
        # Checks that booking for an unknown screening is rejected
        with self.subTest("unknown screening"):
            # Checks the rejection is raised
            with self.assertRaises(ProcessingException):
                # Attempts the booking
                manager.book_seat(99, 1, 1)
        # Checks that a seat outside the room is rejected
        with self.subTest("seat outside room"):
            # Checks the rejection is raised
            with self.assertRaises(ProcessingException):
                # Attempts the booking on row 3, which does not exist
                manager.book_seat(1, 3, 1)
        # Checks that a seat already booked is rejected
        with self.subTest("seat already booked"):
            # Books the seat once
            self.assertEqual(manager.book_seat(1, 1, 1), 1)
            # Checks the second booking of the same seat is rejected
            with self.assertRaises(ProcessingException):
                # Attempts the same seat again
                manager.book_seat(1, 1, 1)

    # Checks cancellation: refund retries, refund failures, gateway unavailability and booking rules
    def test_cancel_booking(self):
        # Builds a manager whose gateway follows the given refund effects, with a clock at the given time, and books seat 1,1
        def build_manager(refund_effect, now):
            # Creates the mocked gateway
            gateway = Mock()
            # Makes the gateway follow the given effects
            gateway.refund.side_effect = refund_effect
            # Creates the manager with the gateway and a mocked clock returning the given time
            manager = SeatBookingManager(gateway, Mock(return_value=now))
            # Registers a screening with two rows of three seats at 1500 cents
            manager.add_screening(Screening(1, SCREENING_START, 2, 3, 1500))
            # Books seat 1,1 as booking 1
            manager.book_seat(1, 1, 1)
            # Returns the manager and the gateway for the test to inspect
            return manager, gateway

        # Sets a clock three hours before the screening, which allows cancellation
        early = SCREENING_START - timedelta(hours=3)
        # Sets a clock one hour before the screening, which is inside the cutoff
        late = SCREENING_START - timedelta(hours=1)
        # Checks that a successful refund cancels the booking and refunds the full price
        with self.subTest("refund succeeds"):
            # Builds a manager whose refund goes through on the first attempt
            manager, gateway = build_manager([None], early)
            # Cancels booking 1
            manager.cancel_booking(1)
            # Checks the gateway was asked to refund the full price
            gateway.refund.assert_called_once_with(1, 1500)
        # Checks that a transient failure is retried and the retry succeeds
        with self.subTest("transient failure then success"):
            # Builds a manager whose first refund fails transiently and whose retry goes through
            manager, gateway = build_manager([GatewayTransientError(), None], early)
            # Cancels booking 1
            manager.cancel_booking(1)
            # Checks the refund was attempted twice
            self.assertEqual(gateway.refund.call_count, 2)
        # Checks that a transient failure is retried three times and then rejected
        with self.subTest("transient failures exhaust retries"):
            # Builds a manager whose refund always fails transiently
            manager, gateway = build_manager([GatewayTransientError()] * 4, early)
            # Checks the cancellation is rejected after the retries
            with self.assertRaises(ProcessingException):
                # Attempts the cancellation
                manager.cancel_booking(1)
            # Checks the refund was attempted four times: one attempt plus three retries
            self.assertEqual(gateway.refund.call_count, 4)
        # Checks that a permanent refund failure rejects the cancellation without retrying
        with self.subTest("permanent failure"):
            # Builds a manager whose refund always fails permanently
            manager, gateway = build_manager([GatewayPermanentError()], early)
            # Checks the cancellation is rejected
            with self.assertRaises(ProcessingException):
                # Attempts the cancellation
                manager.cancel_booking(1)
            # Checks the refund was attempted only once
            self.assertEqual(gateway.refund.call_count, 1)
        # Checks that an unavailable gateway rejects the cancellation without retrying
        with self.subTest("gateway unavailable"):
            # Builds a manager whose gateway is unavailable
            manager, gateway = build_manager([GatewayUnavailableError()], early)
            # Checks the cancellation is rejected
            with self.assertRaises(ProcessingException):
                # Attempts the cancellation
                manager.cancel_booking(1)
            # Checks the refund was attempted only once
            self.assertEqual(gateway.refund.call_count, 1)
        # Checks that cancelling an unknown booking is rejected without touching the gateway
        with self.subTest("unknown booking"):
            # Builds a manager that would succeed at refunding
            manager, gateway = build_manager([None], early)
            # Checks the cancellation of an unknown booking is rejected
            with self.assertRaises(ProcessingException):
                # Attempts to cancel booking 99
                manager.cancel_booking(99)
            # Checks the gateway was not called
            gateway.refund.assert_not_called()
        # Checks that cancelling inside the two-hour cutoff is rejected without touching the gateway
        with self.subTest("too late to cancel"):
            # Builds a manager whose clock is inside the cutoff
            manager, gateway = build_manager([None], late)
            # Checks the cancellation is rejected
            with self.assertRaises(ProcessingException):
                # Attempts the cancellation
                manager.cancel_booking(1)
            # Checks the gateway was not called
            gateway.refund.assert_not_called()
        # Checks that cancelling exactly two hours before the start is still allowed
        with self.subTest("exactly two hours before start"):
            # Builds a manager whose clock is exactly at the cutoff
            manager, gateway = build_manager([None], SCREENING_START - timedelta(hours=2))
            # Cancels booking 1
            manager.cancel_booking(1)
            # Checks the refund went through
            gateway.refund.assert_called_once_with(1, 1500)
        # Checks that cancelling an already cancelled booking is rejected
        with self.subTest("already cancelled"):
            # Builds a manager whose refund goes through
            manager, gateway = build_manager([None], early)
            # Cancels booking 1 once
            manager.cancel_booking(1)
            # Checks the second cancellation is rejected
            with self.assertRaises(ProcessingException):
                # Attempts to cancel booking 1 again
                manager.cancel_booking(1)

    # Checks the refund status of a booking, from not requested to refunded, and unknown bookings
    def test_get_refund_status(self):
        # Creates a gateway whose refund goes through
        gateway = Mock()
        # Builds the manager with a clock three hours before the screening
        manager = SeatBookingManager(gateway, Mock(return_value=SCREENING_START - timedelta(hours=3)))
        # Registers a screening with two rows of three seats
        manager.add_screening(Screening(1, SCREENING_START, 2, 3, 1500))
        # Books seat 1,1 as booking 1
        manager.book_seat(1, 1, 1)
        # Checks that a new booking has no refund requested
        with self.subTest("not requested"):
            # Checks the refund status of booking 1
            self.assertEqual(manager.get_refund_status(1), NOT_REQUESTED)
        # Checks that a refund that went through is exposed as refunded
        with self.subTest("refunded"):
            # Cancels booking 1 so the refund goes through
            manager.cancel_booking(1)
            # Checks the refund status of booking 1
            self.assertEqual(manager.get_refund_status(1), REFUNDED)
        # Checks that an unknown booking is rejected
        with self.subTest("unknown booking"):
            # Checks the lookup is rejected
            with self.assertRaises(ProcessingException):
                # Looks up booking 99
                manager.get_refund_status(99)
