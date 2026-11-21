# unittest is the standard-library test framework
import unittest

# Classes under test
from seat_booking import (
    ProcessingException, SeatAlreadyBookedException, SeatBookingManager)


# One test class for SeatBookingManager, one test (plus numbered variants) per method
class SeatBookingManagerTest(unittest.TestCase):
    # Build a manager with one 2x3 room and one screening
    def setUp(self):
        # Fresh manager for each test
        self.manager = SeatBookingManager()
        # Room with 2 rows of 3 seats
        self.manager.add_room("r1", 2, 3)
        # Screening in that room
        self.manager.add_screening("s1", "r1")

    # add_room: nominal
    def test_add_room(self):
        # A second room can be added
        self.manager.add_room("r2", 1, 1)
        # It is stored
        self.assertEqual(self.manager.rooms["r2"], (1, 1))

    # add_room: invalid size
    def test_add_room2(self):
        # Zero rows is rejected
        with self.assertRaises(ProcessingException):
            self.manager.add_room("r2", 0, 3)

    # add_room: duplicate id
    def test_add_room3(self):
        # Duplicate id is rejected
        with self.assertRaises(ProcessingException):
            self.manager.add_room("r1", 2, 3)

    # add_screening: nominal
    def test_add_screening(self):
        # A second screening can be added
        self.manager.add_screening("s2", "r1")
        # It starts with no booking
        self.assertEqual(self.manager.bookings["s2"], {})

    # add_screening: unknown room
    def test_add_screening2(self):
        # Unknown room is rejected
        with self.assertRaises(ProcessingException):
            self.manager.add_screening("s2", "nope")

    # add_screening: duplicate id
    def test_add_screening3(self):
        # Duplicate id is rejected
        with self.assertRaises(ProcessingException):
            self.manager.add_screening("s1", "r1")

    # book_seat: nominal
    def test_book_seat(self):
        # Book a seat
        self.manager.book_seat("s1", "alice", 1, 2)
        # The seat is no longer available
        self.assertFalse(self.manager.get_seat_availability("s1")[(1, 2)])

    # book_seat: the seat is already booked, even by the same client
    def test_book_seat2(self):
        # First booking succeeds
        self.manager.book_seat("s1", "alice", 1, 2)
        # Second booking by another client is rejected
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", "bob", 1, 2)
        # The original holder is unchanged
        self.assertEqual(self.manager.bookings["s1"][(1, 2)], "alice")

    # book_seat: unknown screening
    def test_book_seat3(self):
        # Unknown screening is rejected
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("nope", "alice", 1, 1)

    # book_seat: seat outside the room
    def test_book_seat4(self):
        # Row out of range is rejected
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("s1", "alice", 3, 1)
        # Seat out of range is rejected
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("s1", "alice", 1, 0)

    # book_seat: same seat, different screening is independent
    def test_book_seat5(self):
        # Second screening in the same room
        self.manager.add_screening("s2", "r1")
        # Book on the first screening
        self.manager.book_seat("s1", "alice", 1, 1)
        # Same seat on the second screening is still free
        self.manager.book_seat("s2", "bob", 1, 1)

    # get_seat_availability: every seat is listed
    def test_get_seat_availability(self):
        # Fresh screening
        availability = self.manager.get_seat_availability("s1")
        # 2 rows x 3 seats, all free
        self.assertEqual(len(availability), 6)
        # Everything is available
        self.assertTrue(all(availability.values()))

    # get_seat_availability: reflects bookings only for booked seats
    def test_get_seat_availability2(self):
        # Book one seat
        self.manager.book_seat("s1", "alice", 2, 3)
        # Read availability
        availability = self.manager.get_seat_availability("s1")
        # Only that seat is taken
        self.assertEqual([k for k, v in availability.items() if not v], [(2, 3)])

    # get_seat_availability: unknown screening
    def test_get_seat_availability3(self):
        # Unknown screening is rejected
        with self.assertRaises(ProcessingException):
            self.manager.get_seat_availability("nope")
