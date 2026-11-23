import unittest

from seat_booking.service import (
    BookingService,
    Room,
    Screening,
    Seat,
    SeatAlreadyBookedError,
    UnknownScreeningError,
    UnknownSeatError,
)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.room = Room("A", (2, 3))
        self.service.add_screening(Screening("s1", "Film", self.room))
        self.service.add_screening(Screening("s2", "Film", self.room))

    def test_room_lists_every_seat(self):
        self.assertEqual(len(self.room.seats()), 5)

    def test_room_rejects_empty(self):
        with self.assertRaises(ValueError):
            Room("x", ())
        with self.assertRaises(ValueError):
            Room("x", (2, 0))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(len(availability), 5)
        self.assertTrue(all(availability.values()))

    def test_book_marks_seat_unavailable(self):
        self.service.book("s1", "alice", 2, 3)
        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat(2, 3)])
        self.assertTrue(availability[Seat(2, 2)])

    def test_double_booking_rejected(self):
        self.service.book("s1", "alice", 1, 1)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", 1, 1)

    def test_same_seat_other_screening_is_independent(self):
        self.service.book("s1", "alice", 1, 1)
        self.service.book("s2", "bob", 1, 1)
        self.assertTrue(self.service.availability("s2")[Seat(1, 2)])

    def test_unknown_seat_rejected(self):
        with self.assertRaises(UnknownSeatError):
            self.service.book("s1", "alice", 1, 3)

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", 1, 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_rejected(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "Film", self.room))


if __name__ == "__main__":
    unittest.main()
