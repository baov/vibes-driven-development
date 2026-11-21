import unittest

from seat_booking.booking import (
    BookingService, Room, Screening, Seat,
    SeatAlreadyBookedError, UnknownScreeningError, UnknownSeatError,
)


class BookingTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.room = Room("A", rows=2, seats_per_row=3)
        self.service.add_screening(Screening("s1", "Film", self.room))
        self.service.add_screening(Screening("s2", "Film", self.room))

    def test_book_free_seat(self):
        booking = self.service.book("s1", Seat(1, 1), "alice")
        self.assertEqual(booking.client, "alice")
        self.assertFalse(self.service.availability("s1")[Seat(1, 1)])

    def test_double_booking_rejected_even_for_other_client(self):
        self.service.book("s1", Seat(1, 1), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", Seat(1, 1), "bob")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", Seat(1, 1), "alice")

    def test_same_seat_other_screening_is_independent(self):
        self.service.book("s1", Seat(1, 1), "alice")
        self.service.book("s2", Seat(1, 1), "bob")

    def test_availability_lists_every_seat(self):
        self.service.book("s1", Seat(2, 3), "alice")
        availability = self.service.availability("s1")
        self.assertEqual(set(availability), set(self.room.seats()))
        self.assertEqual(len(availability), 6)
        self.assertEqual([s for s, free in availability.items() if not free], [Seat(2, 3)])
        self.assertTrue(all(self.service.availability("s2").values()))

    def test_unknown_seat_and_screening(self):
        for seat in (Seat(0, 1), Seat(3, 1), Seat(1, 4), Seat(1, 0)):
            with self.assertRaises(UnknownSeatError):
                self.service.book("s1", seat, "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", Seat(1, 1), "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_invalid_room_and_duplicate_screening(self):
        with self.assertRaises(ValueError):
            Room("bad", 0, 5)
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", "Other", self.room))


if __name__ == "__main__":
    unittest.main()
