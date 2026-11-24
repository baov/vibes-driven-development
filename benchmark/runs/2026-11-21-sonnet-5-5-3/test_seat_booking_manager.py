# Import unittest, the test framework available in the standard library.
import unittest
# Import MagicMock to stand in for the collaborators of the manager.
from unittest.mock import MagicMock

# Import the class under test and its exceptions.
from seat_booking import ProcessingException, SeatAlreadyBookedException, SeatBookingManager


# Build a mocked screening of 2 rows with 3 seats each.
def make_screening_helper(screening_id="s1"):
    # Mocked room collaborator.
    room = MagicMock(row_count=2, seats_per_row=3)
    # Mocked screening collaborator.
    return MagicMock(screening_id=screening_id, room=room)


# One test class for the one production class, one test per public method.
class SeatBookingManagerTest(unittest.TestCase):

    # Test of register_screening.
    def test_register_screening(self):
        # Manager under test.
        manager = SeatBookingManager()
        # Register a screening.
        manager.register_screening(make_screening_helper())
        # A registered screening is listed with its 6 seats.
        self.assertEqual(6, len(manager.get_seat_availability("s1")))

    # Test of book_seat: nominal case and every rejection.
    def test_book_seat(self):
        # Manager under test.
        manager = SeatBookingManager()
        # Register a screening.
        manager.register_screening(make_screening_helper())
        # Book a free seat.
        manager.book_seat("s1", 1, 2, "alice")
        # Booking the same seat again is rejected, even for the same client.
        with self.assertRaises(SeatAlreadyBookedException):
            manager.book_seat("s1", 1, 2, "bob")
        # A seat outside the room is rejected.
        with self.assertRaises(ProcessingException):
            manager.book_seat("s1", 3, 1, "bob")
        # An unknown screening is rejected.
        with self.assertRaises(ProcessingException):
            manager.book_seat("nope", 1, 1, "bob")

    # Test of get_seat_availability: booked seats are unavailable, others are free.
    def test_get_seat_availability(self):
        # Manager under test.
        manager = SeatBookingManager()
        # Register two screenings of the same shape.
        manager.register_screening(make_screening_helper("s1"))
        # Second screening must stay unaffected by bookings on the first.
        manager.register_screening(make_screening_helper("s2"))
        # Book one seat on the first screening only.
        manager.book_seat("s1", 2, 3, "alice")
        # Seats currently available on each screening.
        data = {s: [(i["row"], i["seat"]) for i in manager.get_seat_availability(s) if i["available"]]
                for s in ("s1", "s2")}
        # Exactly the booked seat is missing, and only on its own screening.
        self.assertEqual((5, 6), (len(data["s1"]), len(data["s2"])))
        # The booked seat is the one reported unavailable.
        self.assertNotIn((2, 3), data["s1"])
        # An unknown screening is rejected.
        with self.assertRaises(ProcessingException):
            manager.get_seat_availability("nope")


# Allow running this file directly.
if __name__ == "__main__":
    # Run the tests.
    unittest.main()
