# unittest is the test framework.
import unittest
# Silence expected error logs during tests.
import logging

# Class under test and its generic exception.
from seat_booking.seat_booking_manager import ProcessingException, SeatBookingManager


# One test file for the class SeatBookingManager, one test per public method.
class SeatBookingManagerTest(unittest.TestCase):

    # Keep expected failures out of the test output.
    def setUp(self):
        # Disable logging below CRITICAL.
        logging.disable(logging.CRITICAL)
        # Re-enable logging after each test.
        self.addCleanup(logging.disable, logging.NOTSET)

    # Test of add_room: nominal case and invalid room.
    def test_add_room(self):
        # Fresh manager; SeatBookingManager has no collaborator to mock.
        manager = SeatBookingManager()
        # Nominal case.
        manager.add_room("r1", 2, 3)
        # Invalid room must be rejected.
        with self.assertRaises(ProcessingException):
            manager.add_room("r2", 0, 3)

    # Test of add_screening: nominal case and unknown room.
    def test_add_screening(self):
        # Fresh manager.
        manager = SeatBookingManager()
        # Prepare a room.
        manager.add_room("r1", 2, 3)
        # Nominal case.
        manager.add_screening("s1", "r1")
        # Unknown room must be rejected.
        with self.assertRaises(ProcessingException):
            manager.add_screening("s2", "nope")

    # Test of book_seat: nominal, double booking, unknown screening, unknown seat.
    def test_book_seat(self):
        # Fresh manager.
        manager = SeatBookingManager()
        # Prepare a room and a screening.
        manager.add_room("r1", 2, 3)
        manager.add_screening("s1", "r1")
        # Nominal case.
        manager.book_seat("s1", "alice", 1, 1)
        # Booking an already booked seat must be rejected.
        with self.assertRaises(ProcessingException):
            manager.book_seat("s1", "bob", 1, 1)
        # Unknown screening must be rejected.
        with self.assertRaises(ProcessingException):
            manager.book_seat("nope", "bob", 1, 1)
        # Seat outside of the room must be rejected.
        with self.assertRaises(ProcessingException):
            manager.book_seat("s1", "bob", 9, 9)

    # Test of get_availability: nominal and unknown screening.
    def test_get_availability(self):
        # Fresh manager.
        manager = SeatBookingManager()
        # Prepare a room, a screening and one booking.
        manager.add_room("r1", 2, 3)
        manager.add_screening("s1", "r1")
        manager.book_seat("s1", "alice", 1, 1)
        # Nominal case: one entry per seat, 2 x 3 = 6.
        self.assertEqual(len(manager.get_availability("s1")), 6)
        # Unknown screening must be rejected.
        with self.assertRaises(ProcessingException):
            manager.get_availability("nope")


# Allow running this file directly.
if __name__ == "__main__":
    # Run the tests.
    unittest.main()
