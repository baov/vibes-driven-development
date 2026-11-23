import unittest

from seat_booking import (BookingService, Room, Screening, Seat,
                          SeatAlreadyBookedError, UnknownScreeningError,
                          UnknownSeatError)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.service.add_screening(Screening("s1", "Film", Room("A", 2, 3)))
        self.service.add_screening(Screening("s2", "Film", Room("A", 2, 3)))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(len(availability), 6)
        self.assertTrue(all(availability.values()))

    def test_book_marks_seat_unavailable(self):
        self.service.book("s1", "alice", 1, 2)
        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat(1, 2)])
        self.assertEqual(sum(availability.values()), 5)

    def test_double_booking_rejected_even_for_same_client(self):
        self.service.book("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "alice", 1, 2)

    def test_bookings_are_per_screening(self):
        self.service.book("s1", "alice", 1, 2)
        self.assertTrue(self.service.availability("s2")[Seat(1, 2)])
        self.service.book("s2", "bob", 1, 2)

    def test_unknown_seat_rejected(self):
        for row, number in [(0, 1), (3, 1), (1, 4), (1, 0)]:
            with self.assertRaises(UnknownSeatError):
                self.service.book("s1", "alice", row, number)

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", 1, 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_invalid_room_and_duplicate_screening(self):
        with self.assertRaises(ValueError):
            Room("bad", 0, 5)
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "Film", Room("A", 1, 1)))


if __name__ == "__main__":
    unittest.main()
