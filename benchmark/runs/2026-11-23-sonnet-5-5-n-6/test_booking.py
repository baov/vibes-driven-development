import unittest

from seat_booking import (BookingService, Room, Screening, Seat,
                          SeatAlreadyBookedError, UnknownScreeningError,
                          UnknownSeatError)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.room = Room("A", rows=2, seats_per_row=3)
        self.service.add_screening(Screening("s1", "Film", self.room))
        self.service.add_screening(Screening("s2", "Film", self.room))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(len(availability), 6)
        self.assertTrue(all(availability.values()))

    def test_booking_marks_only_that_seat_unavailable(self):
        self.service.book("s1", "alice", 1, 2)
        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat(1, 2)])
        self.assertEqual(sum(not v for v in availability.values()), 1)

    def test_double_booking_rejected(self):
        self.service.book("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "alice", 1, 2)

    def test_same_seat_other_screening_is_independent(self):
        self.service.book("s1", "alice", 1, 2)
        self.service.book("s2", "bob", 1, 2)
        self.assertTrue(self.service.availability("s2")[Seat(2, 1)])
        self.assertFalse(self.service.availability("s2")[Seat(1, 2)])

    def test_unknown_seat_rejected(self):
        for row, number in [(0, 1), (3, 1), (1, 4), (1, 0)]:
            with self.assertRaises(UnknownSeatError):
                self.service.book("s1", "alice", row, number)

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", 1, 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_and_invalid_room(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "Film", self.room))
        with self.assertRaises(ValueError):
            Room("B", rows=0, seats_per_row=1)


if __name__ == "__main__":
    unittest.main()
