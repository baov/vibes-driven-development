# Import the unittest framework.
import unittest
# Import the mock helpers used to replace collaborators.
from unittest.mock import Mock

# Import the class under test and the exceptions it raises.
from seat_booking import ProcessingException, Room, SeatAlreadyBookedException, SeatBookingManager


# Mirrors the SeatBookingManager class in seat_booking/__init__.py.
class TestSeatBookingManager(unittest.TestCase):

    # Prepares a manager with one screening "s1" whose mocked room has two seats.
    def setUp(self):
        # Mock the room collaborator so that the manager runs no real room logic.
        self.room = Mock(spec=Room)
        # Answer that only the seats (1, 1) and (1, 2) exist.
        self.room.has_seat.side_effect = lambda row, seat: (row, seat) in [(1, 1), (1, 2)]
        # Answer that the room lists the two seats.
        self.room.seats.return_value = [(1, 1), (1, 2)]
        # Create the manager under test.
        self.manager = SeatBookingManager()
        # Register the mocked room as screening "s1".
        self.manager.add_screening("s1", self.room)

    # Checks that a new manager knows no screening.
    def test___init__(self):
        # Create a fresh manager with no screening.
        manager = SeatBookingManager()
        # Check that looking up any screening is rejected.
        with self.assertRaises(ProcessingException):
            # Ask the fresh manager for the availability of an unknown screening.
            manager.seat_availability("s1")

    # Checks that a registered screening exposes the seats of its room.
    def test_add_screening(self):
        # Register a second screening in the same mocked room.
        self.manager.add_screening("s2", self.room)
        # Check that the new screening lists all its seats as available.
        self.assertEqual(self.manager.seat_availability("s2"), {(1, 1): True, (1, 2): True})

    # Checks that a free seat becomes booked.
    def test_book_seat(self):
        # Book seat (1, 1) of screening "s1" for client "c1".
        self.manager.book_seat("s1", 1, 1, "c1")
        # Check that the seat is no longer available.
        self.assertFalse(self.manager.seat_availability("s1")[(1, 1)])

    # Checks that booking a seat of an unknown screening is rejected.
    def test_book_seat_unknown_screening(self):
        # Check that the booking raises a processing error.
        with self.assertRaises(ProcessingException):
            # Book a seat of a screening that does not exist.
            self.manager.book_seat("unknown", 1, 1, "c1")

    # Checks that booking a seat the room does not have is rejected.
    def test_book_seat_unknown_seat(self):
        # Check that the booking raises a processing error.
        with self.assertRaises(ProcessingException):
            # Book a seat number that the room does not have.
            self.manager.book_seat("s1", 1, 9, "c1")

    # Checks that booking a seat that is already booked is rejected.
    def test_book_seat_already_booked(self):
        # Book seat (1, 1) once for client "c1".
        self.manager.book_seat("s1", 1, 1, "c1")
        # Check that a second booking of the same seat is rejected with the dedicated error.
        with self.assertRaises(SeatAlreadyBookedException):
            # Try to book the same seat again for client "c2".
            self.manager.book_seat("s1", 1, 1, "c2")

    # Checks that the availability covers every seat of the room, with booked seats marked.
    def test_seat_availability(self):
        # Book seat (1, 2) for client "c1".
        self.manager.book_seat("s1", 1, 2, "c1")
        # Check that seat (1, 1) is free and seat (1, 2) is booked.
        self.assertEqual(self.manager.seat_availability("s1"), {(1, 1): True, (1, 2): False})

    # Checks that the availability of an unknown screening is rejected.
    def test_seat_availability_unknown_screening(self):
        # Check that the lookup raises a processing error.
        with self.assertRaises(ProcessingException):
            # Ask for the availability of a screening that does not exist.
            self.manager.seat_availability("unknown")
