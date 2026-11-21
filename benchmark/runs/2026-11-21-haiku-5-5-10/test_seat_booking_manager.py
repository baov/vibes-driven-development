# Standard library test framework providing the test case and its assertions
import unittest
# Standard library mocking, used to replace the logger collaborator during tests
from unittest import mock

# Production code under test: the service and the exception it raises
from seat_booking import ProcessingException, SeatBookingManager


# Test case that mirrors SeatBookingManager: one test method per public method
class SeatBookingManagerTest(unittest.TestCase):
    # Prepares a fresh service with one registered screening before each test
    def setUp(self):
        # Create a new service so that no state leaks between tests
        self.manager = SeatBookingManager()
        # Replace the module logger, the only collaborator of the service, with a mock
        logger_patch = mock.patch("seat_booking.logger")
        # Activate the replacement for the current test
        logger_patch.start()
        # Restore the real logger after the test, even when the test fails
        self.addCleanup(logger_patch.stop)
        # Register a screening whose room has 2 rows of 3 seats
        self.manager.register_screening("s1", 2, 3)

    # Verifies that invalid and duplicate registrations are rejected
    def test_register_screening(self):
        # A room without any seat must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the invalid registration
            self.manager.register_screening("s2", 0, 3)
        # A screening already registered must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the duplicate registration
            self.manager.register_screening("s1", 2, 3)

    # Verifies that free seats can be booked and that every other booking is rejected
    def test_book_seat(self):
        # Booking a free seat of a registered screening must succeed without raising
        self.manager.book_seat("s1", 1, 1, "c1")
        # Booking the same seat again must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat held by another client
            self.manager.book_seat("s1", 1, 1, "c2")
        # Booking a seat of an unknown screening must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking on an unregistered screening
            self.manager.book_seat("unknown", 1, 1, "c1")
        # Booking a row outside the room must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking on a row that does not exist
            self.manager.book_seat("s1", 3, 1, "c1")

    # Verifies that the availability listing covers every seat and marks the booked ones
    def test_get_seat_availability(self):
        # Hold one seat so that the listing contains a taken entry
        self.manager.book_seat("s1", 1, 2, "c1")
        # Ask for the availability of every seat of the screening
        availability = self.manager.get_seat_availability("s1")
        # Build the expected listing: six seats in row-major order, only seat 1-2 taken
        expected = [{"row": row, "seat": seat, "available": (row, seat) != (1, 2)} for row in (1, 2) for seat in (1, 2, 3)]
        # The listing must match the expected seats and their availability
        self.assertEqual(availability, expected)
        # Querying an unknown screening must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the query on an unregistered screening
            self.manager.get_seat_availability("unknown")
