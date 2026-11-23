import unittest

from seat_booking.service import (
    BookingService, Room, Screening, Seat,
    SeatAlreadyBookedError, UnknownScreeningError, UnknownSeatError,
)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        room = Room("A", rows=2, seats_per_row=3)
        self.service.add_screening(Screening("s1", "Film", room))
        self.service.add_screening(Screening("s2", "Film", room))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(len(availability), 6)
        self.assertTrue(all(availability.values()))

    def test_booking_marks_only_that_seat_unavailable(self):
        self.service.book("s1", "alice", Seat(1, 2))
        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat(1, 2)])
        self.assertEqual(sum(not v for v in availability.values()), 1)

    def test_double_booking_rejected_even_for_same_client(self):
        self.service.book("s1", "alice", Seat(1, 1))
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", Seat(1, 1))
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "alice", Seat(1, 1))

    def test_same_seat_other_screening_is_independent(self):
        self.service.book("s1", "alice", Seat(1, 1))
        self.service.book("s2", "bob", Seat(1, 1))
        self.assertTrue(self.service.availability("s2")[Seat(2, 1)])

    def test_unknown_seat_rejected(self):
        for seat in (Seat(0, 1), Seat(3, 1), Seat(1, 4)):
            with self.assertRaises(UnknownSeatError):
                self.service.book("s1", "alice", seat)

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", Seat(1, 1))
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_and_invalid_room(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "X", Room("B", 1, 1)))
        with self.assertRaises(ValueError):
            Room("bad", 0, 5)


if __name__ == "__main__":
    unittest.main()
