"""Tests for SeatBookingManager and related classes."""

import unittest
from seat_booking.service import (
    Room, Screening, SeatBookingManager, BookingException, ProcessingException
)


class TestRoom(unittest.TestCase):
    """Tests for Room entity."""

    def test_init(self):
        # Create a room and verify its attributes.
        room = Room("room1", 3, 10)
        self.assertEqual(room.room_id, "room1")
        self.assertEqual(room.rows, 3)
        self.assertEqual(room.seats_per_row, 10)


class TestScreening(unittest.TestCase):
    """Tests for Screening entity."""

    def test_init(self):
        # Create a screening and verify its attributes.
        room = Room("room1", 3, 10)
        screening = Screening("screening1", room)
        self.assertEqual(screening.screening_id, "screening1")
        self.assertIs(screening.room, room)


class TestSeatBookingManager(unittest.TestCase):
    """Tests for SeatBookingManager service."""

    def setUp(self):
        # Set up test fixtures for each test.
        self.manager = SeatBookingManager()
        self.room = Room("room1", 3, 10)
        self.screening = Screening("screening1", self.room)

    def test_book_seat_valid(self):
        # Booking a valid seat succeeds.
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        # Verify the seat is booked by checking availability.
        availability = self.manager.get_availability(self.screening)
        self.assertEqual(availability[(0, 0)], "Alice")

    def test_book_seat_duplicate_raises_exception(self):
        # Booking the same seat twice raises BookingException.
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        with self.assertRaises(BookingException):
            self.manager.book_seat(self.screening, 0, 0, "Bob")

    def test_book_seat_invalid_row_negative(self):
        # Booking a negative row raises BookingException.
        with self.assertRaises(BookingException):
            self.manager.book_seat(self.screening, -1, 0, "Alice")

    def test_book_seat_invalid_row_too_large(self):
        # Booking a row at or beyond the room's row count raises BookingException.
        with self.assertRaises(BookingException):
            self.manager.book_seat(self.screening, 3, 0, "Alice")

    def test_book_seat_invalid_seat_negative(self):
        # Booking a negative seat raises BookingException.
        with self.assertRaises(BookingException):
            self.manager.book_seat(self.screening, 0, -1, "Alice")

    def test_book_seat_invalid_seat_too_large(self):
        # Booking a seat at or beyond seats_per_row raises BookingException.
        with self.assertRaises(BookingException):
            self.manager.book_seat(self.screening, 0, 10, "Alice")

    def test_book_seat_multiple_different_seats(self):
        # Booking multiple different seats succeeds.
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        self.manager.book_seat(self.screening, 0, 1, "Bob")
        self.manager.book_seat(self.screening, 1, 0, "Charlie")
        availability = self.manager.get_availability(self.screening)
        self.assertEqual(availability[(0, 0)], "Alice")
        self.assertEqual(availability[(0, 1)], "Bob")
        self.assertEqual(availability[(1, 0)], "Charlie")

    def test_book_seat_same_seat_different_screenings(self):
        # The same seat in different screenings can be booked independently.
        screening2 = Screening("screening2", self.room)
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        self.manager.book_seat(screening2, 0, 0, "Bob")
        availability1 = self.manager.get_availability(self.screening)
        availability2 = self.manager.get_availability(screening2)
        self.assertEqual(availability1[(0, 0)], "Alice")
        self.assertEqual(availability2[(0, 0)], "Bob")

    def test_get_availability_empty_screening(self):
        # A new screening has all seats available (None).
        availability = self.manager.get_availability(self.screening)
        # Verify all seats are present and available.
        self.assertEqual(len(availability), 30)  # 3 rows * 10 seats
        for row in range(3):
            for seat in range(10):
                self.assertIsNone(availability[(row, seat)])

    def test_get_availability_after_booking(self):
        # Availability reflects booked seats.
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        self.manager.book_seat(self.screening, 1, 5, "Bob")
        availability = self.manager.get_availability(self.screening)
        # Booked seats show the client name.
        self.assertEqual(availability[(0, 0)], "Alice")
        self.assertEqual(availability[(1, 5)], "Bob")
        # Other seats are still None.
        self.assertIsNone(availability[(0, 1)])
        self.assertIsNone(availability[(2, 9)])

    def test_get_availability_different_screening_isolated(self):
        # Availability for one screening is isolated from another.
        screening2 = Screening("screening2", self.room)
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        availability1 = self.manager.get_availability(self.screening)
        availability2 = self.manager.get_availability(screening2)
        # Screening 1 has a booked seat.
        self.assertEqual(availability1[(0, 0)], "Alice")
        # Screening 2 is unaffected.
        self.assertIsNone(availability2[(0, 0)])

    def test_book_seat_edge_case_last_seat(self):
        # Booking the last seat (max row, max seat) succeeds.
        self.manager.book_seat(self.screening, 2, 9, "Alice")
        availability = self.manager.get_availability(self.screening)
        self.assertEqual(availability[(2, 9)], "Alice")

    def test_book_seat_edge_case_first_seat(self):
        # Booking the first seat (0, 0) succeeds.
        self.manager.book_seat(self.screening, 0, 0, "Alice")
        availability = self.manager.get_availability(self.screening)
        self.assertEqual(availability[(0, 0)], "Alice")

    def test_book_seat_bad_room_raises_processing_exception(self):
        # If room lacks expected attributes, ProcessingException is raised.
        bad_screening = Screening("bad1", None)
        with self.assertRaises(ProcessingException):
            self.manager.book_seat(bad_screening, 0, 0, "Alice")

    def test_get_availability_bad_room_raises_processing_exception(self):
        # If room lacks expected attributes, ProcessingException is raised.
        bad_screening = Screening("bad1", None)
        with self.assertRaises(ProcessingException):
            self.manager.get_availability(bad_screening)


if __name__ == "__main__":
    unittest.main()
