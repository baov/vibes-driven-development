# Import unittest, the only test framework available
import unittest

# Import the class under test and its collaborating data/exceptions
from seat_booking import (ProcessingException, Room, Screening,
                          SeatAlreadyBookedException, SeatBookingManager)


# One test file for SeatBookingManager, one test per public method
class SeatBookingManagerTest(unittest.TestCase):
    # Build a manager holding a 2x3 screening
    def setUp(self):
        # Fresh manager for each test
        self.manager = SeatBookingManager()
        # Register a screening in a 2 rows x 3 seats room
        self.manager.add_screening(Screening("s1", Room("r1", 2, 3)))

    # Test for add_screening
    def test_add_screening(self):
        # A newly added screening is retrievable
        self.assertIn("s1", self.manager.screenings)

    # Test for book_seat: nominal, double booking, invalid seat, unknown screening
    def test_book_seat(self):
        # Booking a free seat succeeds
        self.assertEqual(self.manager.book_seat("s1", 1, 1, "alice"), (1, 1))
        # Booking the same seat again is rejected
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", 1, 1, "bob")
        # A seat outside the room is rejected
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("s1", 3, 1, "bob")
        # An unknown screening is rejected
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("nope", 1, 1, "bob")
        # The first client keeps the seat
        self.assertEqual(self.manager.screenings["s1"].bookings[(1, 1)], "alice")

    # Test for get_seat_availability: every seat listed, booked one flagged, unknown screening
    def test_get_seat_availability(self):
        # Book one seat
        self.manager.book_seat("s1", 2, 3, "alice")
        # Read the availability map
        data = self.manager.get_seat_availability("s1")
        # All 6 seats are listed, only (2, 3) is unavailable
        self.assertEqual(data, {(1, 1): True, (1, 2): True, (1, 3): True,
                                (2, 1): True, (2, 2): True, (2, 3): False})
        # An unknown screening is rejected
        with self.assertRaises(ProcessingException):
            self.manager.get_seat_availability("nope")


# Allow running the file directly
if __name__ == "__main__":
    # Run the tests
    unittest.main()
