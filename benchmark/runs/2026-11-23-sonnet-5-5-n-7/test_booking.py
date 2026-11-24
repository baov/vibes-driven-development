import unittest

from seat_booking import (BookingService, InvalidSeatError, Room, Screening,
                          SeatAlreadyBookedError, UnknownScreeningError)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.service.add_screening(Screening("s1", "Film", Room("A", 2, 3)))
        self.service.add_screening(Screening("s2", "Film", Room("A", 2, 3)))

    def test_all_seats_available_initially(self):
        av = self.service.availability("s1")
        self.assertEqual(6, len(av))
        self.assertTrue(all(av.values()))

    def test_booking_marks_seat_unavailable(self):
        self.service.book("s1", "alice", 1, 2)
        av = self.service.availability("s1")
        self.assertFalse(av[(1, 2)])
        self.assertEqual(5, sum(av.values()))

    def test_double_booking_rejected(self):
        self.service.book("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", 1, 2)

    def test_same_seat_other_screening_ok(self):
        self.service.book("s1", "alice", 1, 2)
        self.service.book("s2", "bob", 1, 2)
        self.assertTrue(self.service.availability("s1")[(2, 1)])

    def test_invalid_seat(self):
        for row, seat in [(0, 1), (3, 1), (1, 0), (1, 4)]:
            with self.assertRaises(InvalidSeatError):
                self.service.book("s1", "alice", row, seat)

    def test_unknown_screening(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", 1, 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_and_bad_room(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "X", Room("B", 1, 1)))
        with self.assertRaises(ValueError):
            Room("B", 0, 1)


if __name__ == "__main__":
    unittest.main()
