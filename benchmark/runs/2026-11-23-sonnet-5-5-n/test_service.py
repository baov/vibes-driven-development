import unittest

from seat_booking.service import (
    BookingService, Room, Screening, Seat, SeatAlreadyBookedError,
    UnknownScreeningError, UnknownSeatError,
)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.service.add_screening(Screening("s1", "Film", Room("A", 2, 3)))
        self.service.add_screening(Screening("s2", "Film", Room("A", 2, 3)))

    def test_availability_lists_every_seat_free_initially(self):
        av = self.service.availability("s1")
        self.assertEqual(len(av), 6)
        self.assertTrue(all(av.values()))

    def test_book_marks_seat_unavailable(self):
        self.service.book("s1", "alice", 1, 2)
        av = self.service.availability("s1")
        self.assertFalse(av[Seat(1, 2)])
        self.assertEqual(sum(av.values()), 5)

    def test_double_booking_rejected(self):
        self.service.book("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", 1, 2)

    def test_same_seat_other_screening_is_free(self):
        self.service.book("s1", "alice", 1, 2)
        self.service.book("s2", "bob", 1, 2)
        self.assertFalse(self.service.availability("s2")[Seat(1, 2)])

    def test_unknown_seat_and_screening(self):
        with self.assertRaises(UnknownSeatError):
            self.service.book("s1", "alice", 3, 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_invalid_room_and_duplicate_screening(self):
        with self.assertRaises(ValueError):
            Room("B", 0, 5)
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "Film", Room("A", 1, 1)))


if __name__ == "__main__":
    unittest.main()
