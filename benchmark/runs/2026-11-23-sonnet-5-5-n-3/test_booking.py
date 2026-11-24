import unittest

from seat_booking import (
    BookingService,
    InvalidSeatError,
    Room,
    Screening,
    Seat,
    SeatAlreadyBookedError,
    UnknownScreeningError,
)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.service.add_screening(Screening("s1", "Alien", Room("A", rows=2, seats_per_row=3)))
        self.service.add_screening(Screening("s2", "Heat", Room("A", rows=2, seats_per_row=3)))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(len(availability), 6)
        self.assertTrue(all(availability.values()))

    def test_booking_marks_only_that_seat_unavailable(self):
        self.service.book("s1", Seat(2, 3), "alice")
        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat(2, 3)])
        self.assertEqual(sum(availability.values()), 5)

    def test_double_booking_rejected_even_for_same_client(self):
        self.service.book("s1", Seat(1, 1), "alice")
        for client in ("bob", "alice"):
            with self.assertRaises(SeatAlreadyBookedError):
                self.service.book("s1", Seat(1, 1), client)

    def test_same_seat_other_screening_is_independent(self):
        self.service.book("s1", Seat(1, 1), "alice")
        self.service.book("s2", Seat(1, 1), "bob")
        self.assertFalse(self.service.availability("s2")[Seat(1, 1)])

    def test_invalid_seat_rejected(self):
        for seat in (Seat(0, 1), Seat(3, 1), Seat(1, 4), Seat(1, 0)):
            with self.assertRaises(InvalidSeatError):
                self.service.book("s1", seat, "alice")

    def test_unknown_screening(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", Seat(1, 1), "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_and_empty_room_rejected(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "X", Room("B", 1, 1)))
        with self.assertRaises(ValueError):
            Room("B", 0, 5)


if __name__ == "__main__":
    unittest.main()
