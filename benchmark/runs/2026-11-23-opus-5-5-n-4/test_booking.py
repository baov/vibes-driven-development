import unittest

from seat_booking.booking import (
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
        self.room = Room("Room 1", {"A": 3, "B": 2})
        self.service.add_screening(Screening("s1", self.room))

    def test_all_seats_are_free_for_a_new_screening(self):
        self.assertEqual(
            self.service.availability("s1"),
            {
                Seat("A", 1): True,
                Seat("A", 2): True,
                Seat("A", 3): True,
                Seat("B", 1): True,
                Seat("B", 2): True,
            },
        )

    def test_availability_is_ordered_row_by_row(self):
        self.assertEqual(
            list(self.service.availability("s1")),
            [Seat("A", 1), Seat("A", 2), Seat("A", 3), Seat("B", 1), Seat("B", 2)],
        )

    def test_booked_seat_becomes_unavailable(self):
        self.assertEqual(self.service.book("s1", "A", 2, "alice"), Seat("A", 2))

        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat("A", 2)])
        self.assertEqual(sum(not free for free in availability.values()), 1)

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.service.book("s1", "A", 2, "alice")

        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "A", 2, "bob")
        # Same client booking twice is rejected too.
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "A", 2, "alice")

    def test_bookings_are_scoped_to_their_screening(self):
        self.service.add_screening(Screening("s2", self.room))
        self.service.book("s1", "A", 1, "alice")

        self.service.book("s2", "A", 1, "bob")
        self.assertTrue(self.service.availability("s2")[Seat("A", 2)])
        self.assertFalse(self.service.availability("s2")[Seat("A", 1)])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        for row, number in [("C", 1), ("A", 0), ("A", 4), ("B", 3)]:
            with self.subTest(row=row, number=number):
                with self.assertRaises(UnknownSeatError):
                    self.service.book("s1", row, number, "alice")
        self.assertTrue(all(self.service.availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "A", 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", self.room))


class RoomTest(unittest.TestCase):
    def test_room_requires_rows(self):
        with self.assertRaises(ValueError):
            Room("Empty", {})

    def test_rows_require_at_least_one_seat(self):
        with self.assertRaises(ValueError):
            Room("Bad", {"A": 0})


if __name__ == "__main__":
    unittest.main()
