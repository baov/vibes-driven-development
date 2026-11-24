import unittest

from seat_booking.booking import (
    BookingManager,
    Room,
    Screening,
    SeatAlreadyBookedError,
    UnknownScreeningError,
    UnknownSeatError,
)


class BookingManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = BookingManager()
        self.manager.add_screening(Screening("s1", "Alien", Room("A", rows=2, seats_per_row=3)))
        self.manager.add_screening(Screening("s2", "Heat", Room("A", rows=2, seats_per_row=3)))

    def test_book_available_seat_marks_it_unavailable(self):
        self.manager.book_seat("s1", "alice", 1, 2)
        availability = self.manager.seat_availability("s1")
        self.assertFalse(availability[(1, 2)])
        self.assertEqual(sum(1 for free in availability.values() if not free), 1)

    def test_booking_already_booked_seat_is_rejected(self):
        self.manager.book_seat("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.manager.book_seat("s1", "bob", 1, 2)
        # Same client rebooking is also rejected.
        with self.assertRaises(SeatAlreadyBookedError):
            self.manager.book_seat("s1", "alice", 1, 2)

    def test_same_seat_in_another_screening_is_independent(self):
        self.manager.book_seat("s1", "alice", 1, 2)
        self.manager.book_seat("s2", "bob", 1, 2)
        self.assertTrue(self.manager.seat_availability("s2")[(1, 1)])
        self.assertFalse(self.manager.seat_availability("s2")[(1, 2)])

    def test_availability_lists_every_seat_of_the_room(self):
        availability = self.manager.seat_availability("s1")
        self.assertEqual(set(availability), {(r, s) for r in (1, 2) for s in (1, 2, 3)})
        self.assertTrue(all(availability.values()))

    def test_unknown_seat_is_rejected(self):
        for row, seat in [(0, 1), (3, 1), (1, 0), (1, 4)]:
            with self.assertRaises(UnknownSeatError):
                self.manager.book_seat("s1", "alice", row, seat)
        self.assertTrue(all(self.manager.seat_availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.manager.book_seat("nope", "alice", 1, 1)
        with self.assertRaises(UnknownScreeningError):
            self.manager.seat_availability("nope")

    def test_room_needs_seats(self):
        with self.assertRaises(ValueError):
            Room("empty", rows=0, seats_per_row=5)


if __name__ == "__main__":
    unittest.main()
