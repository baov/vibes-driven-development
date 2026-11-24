import unittest

from seat_booking import (
    BookingManager,
    Room,
    Screening,
    SeatAlreadyBookedException,
    UnknownScreeningException,
    UnknownSeatException,
)


class BookingManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = BookingManager()
        self.manager.add_screening(Screening("s1", "Film", Room("A", 2, 3)))
        self.manager.add_screening(Screening("s2", "Film", Room("A", 2, 3)))

    def test_all_seats_available_initially(self):
        availability = self.manager.seat_availability("s1")
        self.assertEqual(6, len(availability))
        self.assertTrue(all(availability.values()))

    def test_booking_makes_seat_unavailable(self):
        self.manager.book_seat("s1", 1, 2, "alice")
        availability = self.manager.seat_availability("s1")
        self.assertFalse(availability[(1, 2)])
        self.assertEqual(5, sum(availability.values()))

    def test_double_booking_rejected(self):
        self.manager.book_seat("s1", 1, 2, "alice")
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", 1, 2, "bob")

    def test_same_seat_other_screening_is_independent(self):
        self.manager.book_seat("s1", 1, 2, "alice")
        self.manager.book_seat("s2", 1, 2, "bob")
        self.assertTrue(self.manager.seat_availability("s2")[(2, 3)])

    def test_unknown_seat_rejected(self):
        for row, seat in [(0, 1), (3, 1), (1, 0), (1, 4)]:
            with self.assertRaises(UnknownSeatException):
                self.manager.book_seat("s1", row, seat, "alice")

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownScreeningException):
            self.manager.book_seat("nope", 1, 1, "alice")
        with self.assertRaises(UnknownScreeningException):
            self.manager.seat_availability("nope")

    def test_duplicate_screening_and_empty_room_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.add_screening(Screening("s1", "Film", Room("A", 1, 1)))
        with self.assertRaises(ValueError):
            Room("B", 0, 5)


if __name__ == "__main__":
    unittest.main()
