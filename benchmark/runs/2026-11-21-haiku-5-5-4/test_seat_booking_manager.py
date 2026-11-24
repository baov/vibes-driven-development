# Standard library unittest, used to define the test case
import unittest
# Standard library mock, used to replace the module logger collaborator
from unittest import mock

# Import the class under test and the exception it raises
from seat_booking import ProcessingException, SeatBookingManager


# Test case mirroring SeatBookingManager, with one test per public method
class SeatBookingManagerTest(unittest.TestCase):
    # Build a fresh manager with a mocked logger before each test
    def setUp(self):
        # Create the class under test with empty registries
        self.manager = SeatBookingManager()
        # Create a patcher that replaces the module logger
        patcher = mock.patch("seat_booking.logger")
        # Start the patch and keep the mock logger for assertions
        self.logger = patcher.start()
        # Undo the patch once the test finishes
        self.addCleanup(patcher.stop)

    # Test add_room: registers a room, rejects duplicates and logs unexpected failures
    def test_add_room(self):
        # Register a new room with two rows of three seats
        self.manager.add_room("R1", 2, 3)
        # Registering the same room id again must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the duplicate registration
            self.manager.add_room("R1", 2, 3)
        # An unhashable room id causes an unexpected failure that must also be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the registration with an unhashable id
            self.manager.add_room(["bad"], 2, 3)
        # Both rejections must have been logged at this layer
        self.assertEqual(self.logger.exception.call_count, 2)

    # Test add_screening: registers a screening, rejects duplicates and unknown rooms, logs unexpected failures
    def test_add_screening(self):
        # Register the room hosting the screening
        self.manager.add_room("R1", 2, 3)
        # Register a screening in that room
        self.manager.add_screening("S1", "R1")
        # Registering the same screening id again must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the duplicate registration
            self.manager.add_screening("S1", "R1")
        # A screening in a room that is not registered must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the registration with an unknown room
            self.manager.add_screening("S2", "R9")
        # An unhashable screening id causes an unexpected failure that must also be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the registration with an unhashable id
            self.manager.add_screening(["bad"], "R1")
        # All three rejections must have been logged at this layer
        self.assertEqual(self.logger.exception.call_count, 3)

    # Test book_seat: books a free seat, rejects booked, nonexistent and unknown-screening seats, logs unexpected failures
    def test_book_seat(self):
        # Register the room hosting the screening
        self.manager.add_room("R1", 2, 3)
        # Register the screening to book seats for
        self.manager.add_screening("S1", "R1")
        # Book a free seat for a client
        self.manager.book_seat("S1", "client-a", 1, 2)
        # Booking the same seat again must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book the already booked seat
            self.manager.book_seat("S1", "client-b", 1, 2)
        # Booking for a screening that is not registered must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking with an unknown screening
            self.manager.book_seat("S9", "client-b", 1, 1)
        # Booking a row beyond the room layout must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking of a nonexistent row
            self.manager.book_seat("S1", "client-b", 3, 1)
        # An unhashable screening id causes an unexpected failure that must also be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking with an unhashable id
            self.manager.book_seat(["bad"], "client-b", 1, 1)
        # All four rejections must have been logged at this layer
        self.assertEqual(self.logger.exception.call_count, 4)

    # Test get_seat_availability: reports every seat with its status, rejects unknown screenings, logs unexpected failures
    def test_get_seat_availability(self):
        # Register a room with two rows of two seats
        self.manager.add_room("R1", 2, 2)
        # Register the screening held in that room
        self.manager.add_screening("S1", "R1")
        # Book one seat so its availability differs from the others
        self.manager.book_seat("S1", "client-a", 1, 1)
        # Every seat must be reported in row then seat order with its availability
        self.assertEqual(self.manager.get_seat_availability("S1"), [
            # The booked seat is reported as unavailable
            {"row": 1, "seat": 1, "available": False},
            # The free seats are reported as available
            {"row": 1, "seat": 2, "available": True},
            {"row": 2, "seat": 1, "available": True},
            {"row": 2, "seat": 2, "available": True},
        ])
        # Asking for an unknown screening must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the lookup with an unknown screening
            self.manager.get_seat_availability("S9")
        # An unhashable screening id causes an unexpected failure that must also be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the lookup with an unhashable id
            self.manager.get_seat_availability(["bad"])
        # Both rejections must have been logged at this layer
        self.assertEqual(self.logger.exception.call_count, 2)
