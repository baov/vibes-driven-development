import unittest

from seat_booking.booking import (
    BookingService, Room, Screening, SeatAlreadyBookedError,
    UnknownScreeningError, UnknownSeatError,
)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.service.add_screening(Screening("s1", Room("A", 2, 3), "Film"))
        self.service.add_screening(Screening("s2", Room("A", 2, 3), "Film 2"))

    def test_availability_lists_every_seat_free_initially(self):
        av = self.service.availability("s1")
        self.assertEqual(len(av), 6)
        self.assertTrue(all(av.values()))

    def test_booked_seat_becomes_unavailable(self):
        self.service.book_seat("s1", "alice", 1, 2)
        av = self.service.availability("s1")
        self.assertFalse(av[(1, 2)])
        self.assertEqual(sum(av.values()), 5)

    def test_double_booking_rejected_even_for_other_client(self):
        self.service.book_seat("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", "bob", 1, 2)

    def test_same_seat_other_screening_is_independent(self):
        self.service.book_seat("s1", "alice", 1, 2)
        self.service.book_seat("s2", "bob", 1, 2)
        self.assertTrue(self.service.availability("s1")[(2, 1)])

    def test_unknown_seat_rejected(self):
        for rs in [(0, 1), (3, 1), (1, 4), (1, 0)]:
            with self.assertRaises(UnknownSeatError):
                self.service.book_seat("s1", "alice", *rs)

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book_seat("nope", "alice", 1, 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_empty_room_rejected(self):
        with self.assertRaises(ValueError):
            Room("B", 0, 5)


if __name__ == "__main__":
    unittest.main()
