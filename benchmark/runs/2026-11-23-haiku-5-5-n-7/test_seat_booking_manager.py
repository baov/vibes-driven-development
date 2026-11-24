# Standard library test framework
import unittest
# Standard library mocking used to replace the logger collaborator
from unittest import mock

# Production classes under test
from seat_booking import ProcessingException, SeatAlreadyBookedException, SeatBookingManager


# Test case mirroring SeatBookingManager: one test per public method, collaborators mocked
class SeatBookingManagerTest(unittest.TestCase):
    # Prepares a fresh service with a mocked logger for every test
    def setUp(self):
        # Create the patcher that replaces the module logger
        patcher = mock.patch("seat_booking.logger")
        # Activate the patch and keep the mock logger
        self.logger = patcher.start()
        # Undo the patch after the test finishes
        self.addCleanup(patcher.stop)
        # Create the service under test
        self.manager = SeatBookingManager()

    # Verifies that add_screening accepts a valid room and rejects invalid ones
    def test_add_screening(self):
        # Register a valid screening of a 2-row room with 3 seats per row
        self.manager.add_screening("s1", 2, 3)
        # Verify that an invalid room size is rejected with the generic exception
        with self.assertRaises(ProcessingException):
            # Attempt to register a room without rows
            self.manager.add_screening("s2", 0, 3)
        # Verify that a non-numeric room size is wrapped in the generic exception
        with self.assertRaises(ProcessingException):
            # Attempt to register a room whose row count is not a number
            self.manager.add_screening("s3", "two", 3)
        # Verify that the rejections were logged
        self.logger.exception.assert_called()

    # Verifies that book_seat books free seats and rejects seats that are taken, out of range or unknown
    def test_book_seat(self):
        # Register a screening to book seats for
        self.manager.add_screening("s1", 2, 3)
        # Book a free seat for a client
        self.manager.book_seat("s1", 1, 1, "client-a")
        # Verify that booking the same seat again is rejected as already booked
        with self.assertRaises(SeatAlreadyBookedException):
            # Attempt to book the seat that was just taken
            self.manager.book_seat("s1", 1, 1, "client-b")
        # Verify that a seat outside the room is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat in a row that does not exist
            self.manager.book_seat("s1", 3, 1, "client-b")
        # Verify that a booking for an unknown screening is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat of a screening that was never added
            self.manager.book_seat("missing", 1, 1, "client-b")
        # Verify that a non-numeric row is wrapped in the generic exception
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat whose row is not a number
            self.manager.book_seat("s1", "x", 1, "client-b")

    # Verifies that get_seat_availability reports every seat and rejects unknown screenings
    def test_get_seat_availability(self):
        # Register a screening of a 2-row room with 2 seats per row
        self.manager.add_screening("s1", 2, 2)
        # Book one seat so that it appears as unavailable
        self.manager.book_seat("s1", 1, 2, "client-a")
        # Read the availability of every seat of the screening
        availability = self.manager.get_seat_availability("s1")
        # Verify that every seat of the room is reported
        self.assertEqual(len(availability), 4)
        # Verify that an unknown screening is rejected with the generic exception
        with self.assertRaises(ProcessingException):
            # Attempt to read the availability of a screening that was never added
            self.manager.get_seat_availability("missing")
        # Verify that an id that cannot be used as a key is wrapped in the generic exception
        with self.assertRaises(ProcessingException):
            # Attempt to read availability with a list as the screening id
            self.manager.get_seat_availability(["s1"])
