# Import the standard test framework
import unittest
# Import the mocking utilities used to replace the logger collaborator
from unittest import mock
# Import the class under test and the exception it raises at its boundary
from seat_booking import ProcessingException, SeatBookingManager


# Test the SeatBookingManager class, one test per method
class SeatBookingManagerTest(unittest.TestCase):
    # Prepare a fresh manager with a mocked logger before each test
    def setUp(self):
        # Create the manager under test
        self.manager = SeatBookingManager()
        # Patch the module logger, the only collaborator of the manager
        logger_patcher = mock.patch("seat_booking.logger")
        # Start the patch so the logger is replaced
        self.logger = logger_patcher.start()
        # Undo the patch after each test
        self.addCleanup(logger_patcher.stop)

    # Test that add_screening registers a room whose seats are all reported
    def test_add_screening(self):
        # Register a screening in a room with two rows of three seats
        self.manager.add_screening("s1", 2, 3)
        # Check that all six seats of the room are reported
        self.assertEqual(len(self.manager.get_seat_availability("s1")), 6)

    # Test that registering the same screening id twice is rejected and logged
    def test_add_screening_rejects_duplicate(self):
        # Register the screening once
        self.manager.add_screening("s1", 2, 3)
        # Check that the second registration raises the boundary exception
        with self.assertRaises(ProcessingException):
            # Attempt to register the same screening id again
            self.manager.add_screening("s1", 2, 3)
        # Check that the failure was logged
        self.logger.exception.assert_called_once()

    # Test that a room without rows or seats is rejected and logged
    def test_add_screening_rejects_empty_room(self):
        # Check that a room with zero rows raises the boundary exception
        with self.assertRaises(ProcessingException):
            # Attempt to register a screening whose room has no rows
            self.manager.add_screening("s1", 0, 3)
        # Check that the failure was logged
        self.logger.exception.assert_called_once()

    # Test that book_seat marks the requested seat as booked
    def test_book_seat(self):
        # Register a screening in a room with two rows of three seats
        self.manager.add_screening("s1", 2, 3)
        # Book the seat in the first row, second column for a client
        self.manager.book_seat("s1", 1, 2, "client-a")
        # Check that the booked seat is no longer available
        self.assertFalse(self.manager.get_seat_availability("s1")[(1, 2)])

    # Test that booking a seat of an unknown screening is rejected and logged
    def test_book_seat_rejects_unknown_screening(self):
        # Check that booking on an unregistered screening raises the boundary exception
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat on a screening that was never registered
            self.manager.book_seat("missing", 1, 1, "client-a")
        # Check that the failure was logged
        self.logger.exception.assert_called_once()

    # Test that booking a seat outside the room is rejected and logged
    def test_book_seat_rejects_seat_outside_room(self):
        # Register a screening in a room with two rows of three seats
        self.manager.add_screening("s1", 2, 3)
        # Check that a row beyond the room raises the boundary exception
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat in row three, which does not exist
            self.manager.book_seat("s1", 3, 1, "client-a")
        # Check that the failure was logged
        self.logger.exception.assert_called_once()

    # Test that booking an already booked seat is rejected and logged
    def test_book_seat_rejects_booked_seat(self):
        # Register a screening in a room with two rows of three seats
        self.manager.add_screening("s1", 2, 3)
        # Book the seat in the first row, first column for one client
        self.manager.book_seat("s1", 1, 1, "client-a")
        # Check that booking the same seat again raises the boundary exception
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that is already held by another client
            self.manager.book_seat("s1", 1, 1, "client-b")
        # Check that the failure was logged
        self.logger.exception.assert_called_once()

    # Test that get_seat_availability reports every seat with its availability
    def test_get_seat_availability(self):
        # Register a screening in a room with one row of two seats
        self.manager.add_screening("s1", 1, 2)
        # Book the first seat for a client
        self.manager.book_seat("s1", 1, 1, "client-a")
        # Check that the map shows the booked seat as False and the free seat as True
        self.assertEqual(self.manager.get_seat_availability("s1"), {(1, 1): False, (1, 2): True})

    # Test that reading availability of an unknown screening is rejected and logged
    def test_get_seat_availability_rejects_unknown_screening(self):
        # Check that reading an unregistered screening raises the boundary exception
        with self.assertRaises(ProcessingException):
            # Attempt to read the availability of a screening that was never registered
            self.manager.get_seat_availability("missing")
        # Check that the failure was logged
        self.logger.exception.assert_called_once()
