import unittest

from seat_booking.seat_booking_manager import (
    Room, SeatBookingManager, SeatAlreadyBookedException, UnknownSeatException)


class SeatBookingManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = SeatBookingManager()
        self.manager.add_screening("s1", Room(rows=2, seats_per_row=3))

    def test_room_rejects_empty_dimensions(self):
        with self.assertRaises(ValueError):
            Room(0, 3)

    def test_duplicate_screening_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.add_screening("s1", Room(1, 1))

    def test_all_seats_free_initially(self):
        availability = self.manager.get_seat_availability("s1")
        self.assertEqual(6, len(availability))
        self.assertTrue(all(availability.values()))

    def test_booking_marks_only_that_seat_unavailable(self):
        self.manager.book_seat("s1", "alice", 1, 2)
        availability = self.manager.get_seat_availability("s1")
        self.assertFalse(availability[(1, 2)])
        self.assertEqual(5, sum(availability.values()))

    def test_double_booking_rejected_even_for_other_client(self):
        self.manager.book_seat("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", "bob", 1, 2)
        self.assertEqual(5, sum(self.manager.get_seat_availability("s1").values()))

    def test_same_seat_in_other_screening_is_independent(self):
        self.manager.add_screening("s2", Room(2, 3))
        self.manager.book_seat("s1", "alice", 1, 1)
        self.manager.book_seat("s2", "bob", 1, 1)
        self.assertFalse(self.manager.get_seat_availability("s2")[(1, 1)])

    def test_unknown_seat_rejected(self):
        for row, seat in [(0, 1), (3, 1), (1, 0), (1, 4)]:
            with self.assertRaises(UnknownSeatException):
                self.manager.book_seat("s1", "alice", row, seat)

    def test_unknown_screening_rejected(self):
        with self.assertRaises(UnknownSeatException):
            self.manager.book_seat("nope", "alice", 1, 1)
        with self.assertRaises(UnknownSeatException):
            self.manager.get_seat_availability("nope")


if __name__ == "__main__":
    unittest.main()
