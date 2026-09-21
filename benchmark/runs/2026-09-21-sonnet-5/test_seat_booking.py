"""Tests for seat_booking, mirrored one test class per production class."""

# stdlib test framework, per this project's "Python 3, standard library only"
import unittest

# used to fake a collaborator for the unexpected-error branches
from unittest.mock import MagicMock

from seat_booking import (
    BookingManager,
    ProcessingException,
    Room,
    Screening,
    Seat,
    ScreeningNotFoundError,
    SeatAlreadyBookedError,
    SeatNotFoundError,
)


# Mirrors the Seat class: one test per public method.
class TestSeat(unittest.TestCase):
    # covers Seat.is_available in both its true and false branches
    def test_is_available(self):
        # a freshly created seat has no holder yet
        seat = Seat(1, 1)
        self.assertTrue(seat.is_available())
        # once a client holds it, it is no longer available
        seat.booked_by = "client-1"
        self.assertFalse(seat.is_available())


# Mirrors the Room class: one test for its single responsibility, __init__.
class TestRoom(unittest.TestCase):
    # covers Room.__init__
    def test_init(self):
        room = Room("Room A", 2, 3)
        self.assertEqual(room.name, "Room A")
        self.assertEqual(room.rows, 2)
        self.assertEqual(room.seats_per_row, 3)


# Mirrors the Screening class: one test per public method.
class TestScreening(unittest.TestCase):
    # covers Screening.__init__ and Screening.get_seat
    def test_get_seat(self):
        room = Room("Room A", 1, 2)
        screening = Screening("s1", room)
        # a seat that exists in the room's layout is found
        seat = screening.get_seat(1, 1)
        self.assertIsNotNone(seat)
        self.assertTrue(seat.is_available())
        # a seat outside the room's layout does not exist
        self.assertIsNone(screening.get_seat(5, 5))


# Mirrors the BookingManager class: one test per public method, including
# its rejection and unexpected-failure branches.
class TestBookingManager(unittest.TestCase):
    def setUp(self):
        # a small 1-row, 2-seat room shared by the tests below
        self.room = Room("Room A", 1, 2)
        self.screening = Screening("s1", self.room)
        self.manager = BookingManager()
        self.manager.add_screening(self.screening)

    # covers the successful path of book_seat
    def test_book_seat(self):
        self.manager.book_seat("s1", 1, 1, "client-1")
        self.assertFalse(self.screening.get_seat(1, 1).is_available())
        self.assertEqual(self.screening.get_seat(1, 1).booked_by, "client-1")

    # covers book_seat rejecting a seat that is already booked
    def test_book_seat_rejects_already_booked(self):
        self.manager.book_seat("s1", 1, 1, "client-1")
        with self.assertRaises(SeatAlreadyBookedError):
            self.manager.book_seat("s1", 1, 1, "client-2")

    # covers book_seat's screening-not-found branch
    def test_book_seat_unknown_screening(self):
        with self.assertRaises(ScreeningNotFoundError):
            self.manager.book_seat("unknown", 1, 1, "client-1")

    # covers book_seat's seat-not-found branch
    def test_book_seat_unknown_seat(self):
        with self.assertRaises(SeatNotFoundError):
            self.manager.book_seat("s1", 99, 99, "client-1")

    # covers book_seat's generic wrapping of an unexpected collaborator error
    def test_book_seat_wraps_unexpected_error(self):
        broken_screening = MagicMock()
        broken_screening.get_seat.side_effect = RuntimeError("boom")
        self.manager.screenings["broken"] = broken_screening
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("broken", 1, 1, "client-1")

    # covers the successful path of get_availability, mixing booked/free seats
    def test_get_availability(self):
        self.manager.book_seat("s1", 1, 1, "client-1")
        availability = self.manager.get_availability("s1")
        self.assertEqual(
            availability,
            [
                {"row": 1, "number": 1, "available": False},
                {"row": 1, "number": 2, "available": True},
            ],
        )

    # covers get_availability's screening-not-found branch
    def test_get_availability_unknown_screening(self):
        with self.assertRaises(ScreeningNotFoundError):
            self.manager.get_availability("unknown")

    # covers get_availability's generic wrapping of an unexpected error
    def test_get_availability_wraps_unexpected_error(self):
        broken_screening = MagicMock()
        broken_screening.seats.keys.side_effect = RuntimeError("boom")
        self.manager.screenings["broken"] = broken_screening
        with self.assertRaises(ProcessingException):
            self.manager.get_availability("broken")


if __name__ == "__main__":
    unittest.main()
