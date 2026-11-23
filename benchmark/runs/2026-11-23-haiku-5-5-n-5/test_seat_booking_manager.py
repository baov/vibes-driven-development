# Import the unittest framework to define the test case
import unittest
# Import the mock helper to replace the module logger with a collaborator mock
from unittest.mock import patch

# Import the class under test and the exceptions it raises
from seat_booking import ProcessingException, SeatAlreadyBookedException, SeatBookingManager


# Test case mirroring SeatBookingManager, with one test per method
class SeatBookingManagerTest(unittest.TestCase):
    # Prepare a fresh manager and a mocked logger before each test
    def setUp(self):
        # Start patching the module logger so no real logging happens during tests
        logger_patch = patch("seat_booking.logger")
        # Activate the logger patch for the duration of the test
        logger_patch.start()
        # Undo the logger patch once the test finishes
        self.addCleanup(logger_patch.stop)
        # Create a new manager with no screenings registered
        self.manager = SeatBookingManager()

    # Verify that a screening registers with one entry per seat of the room
    def test_add_screening(self):
        # Register a screening in a room of two rows with three seats each
        self.manager.add_screening("s1", 2, 3)
        # Check that the availability lists all six seats of the room
        self.assertEqual(len(self.manager.get_seat_availability("s1")), 6)

    # Verify that registering the same screening twice is rejected
    def test_add_screening_duplicate(self):
        # Register a screening once
        self.manager.add_screening("s1", 2, 3)
        # Check that registering it again raises a processing exception
        with self.assertRaises(ProcessingException):
            # Attempt the duplicate registration
            self.manager.add_screening("s1", 2, 3)

    # Verify that a free seat can be booked for a client
    def test_book_seat(self):
        # Register a screening in a room of two rows with three seats each
        self.manager.add_screening("s1", 2, 3)
        # Book the seat at row 1, seat 2 for client c1
        self.manager.book_seat("s1", "c1", 1, 2)
        # Check that the seat now shows as unavailable
        self.assertFalse(self.manager.get_seat_availability("s1")[1]["available"])

    # Verify that booking a seat that is already booked is rejected
    def test_book_seat_already_booked(self):
        # Register a screening and book one of its seats
        self.manager.add_screening("s1", 2, 3)
        # Book the seat at row 1, seat 2 for client c1
        self.manager.book_seat("s1", "c1", 1, 2)
        # Check that booking the same seat for another client raises the already-booked exception
        with self.assertRaises(SeatAlreadyBookedException):
            # Attempt to book the same seat for client c2
            self.manager.book_seat("s1", "c2", 1, 2)

    # Verify that booking a seat outside the room layout is rejected
    def test_book_seat_nonexistent_seat(self):
        # Register a screening in a room of two rows with three seats each
        self.manager.add_screening("s1", 2, 3)
        # Check that booking a row beyond the room raises a processing exception
        with self.assertRaises(ProcessingException):
            # Attempt to book row 3, which does not exist
            self.manager.book_seat("s1", "c1", 3, 1)

    # Verify that booking a seat of an unknown screening is rejected
    def test_book_seat_unknown_screening(self):
        # Check that booking in a screening that was never registered raises a processing exception
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat in the unknown screening s9
            self.manager.book_seat("s9", "c1", 1, 1)

    # Verify that availability lists every seat with its booking state
    def test_get_seat_availability(self):
        # Register a screening in a room of two rows with two seats each
        self.manager.add_screening("s1", 2, 2)
        # Book the seat at row 2, seat 1
        self.manager.book_seat("s1", "c1", 2, 1)
        # Check that the availability matches the room with only that seat taken
        self.assertEqual(
            self.manager.get_seat_availability("s1"),
            [
                {"row": 1, "seat": 1, "available": True},
                {"row": 1, "seat": 2, "available": True},
                {"row": 2, "seat": 1, "available": False},
                {"row": 2, "seat": 2, "available": True},
            ],
        )

    # Verify that requesting availability of an unknown screening is rejected
    def test_get_seat_availability_unknown_screening(self):
        # Check that asking for an unregistered screening raises a processing exception
        with self.assertRaises(ProcessingException):
            # Attempt to read availability for the unknown screening s9
            self.manager.get_seat_availability("s9")
