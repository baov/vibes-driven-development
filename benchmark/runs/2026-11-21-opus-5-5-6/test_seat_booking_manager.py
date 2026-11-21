import unittest

from seat_booking import (
    Booking,
    Room,
    Screening,
    SeatAlreadyBookedError,
    SeatAvailability,
    SeatBookingManager,
    UnknownScreeningError,
    UnknownSeatError,
)


def make_manager():
    manager = SeatBookingManager()
    manager.add_screening(Screening("s1", Room("Room 1", {"A": 2, "B": 3})))
    manager.add_screening(Screening("s2", Room("Room 1", {"A": 2, "B": 3})))
    return manager


class BookSeatTest(unittest.TestCase):
    def test_books_a_free_seat(self):
        manager = make_manager()
        booking = manager.book_seat("s1", "alice", "B", 3)
        self.assertEqual(Booking("s1", "alice", "B", 3), booking)

    def test_rejects_booking_an_already_booked_seat(self):
        manager = make_manager()
        manager.book_seat("s1", "alice", "A", 1)
        with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "bob", "A", 1)
        # The original booking is kept.
        self.assertEqual("alice", manager.bookings[("s1", "A", 1)].client_id)

    def test_same_client_cannot_book_the_same_seat_twice(self):
        manager = make_manager()
        manager.book_seat("s1", "alice", "A", 1)
        with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "alice", "A", 1)

    def test_same_seat_can_be_booked_for_another_screening(self):
        manager = make_manager()
        manager.book_seat("s1", "alice", "A", 1)
        booking = manager.book_seat("s2", "bob", "A", 1)
        self.assertEqual("bob", booking.client_id)

    def test_rejects_unknown_screening(self):
        manager = make_manager()
        with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(UnknownScreeningError):
            manager.book_seat("nope", "alice", "A", 1)

    def test_rejects_seats_outside_the_room(self):
        manager = make_manager()
        for row, seat in [("Z", 1), ("A", 0), ("A", 3), ("B", 4)]:
            with self.subTest(row=row, seat=seat):
                with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(UnknownSeatError):
                    manager.book_seat("s1", "alice", row, seat)
        self.assertEqual({}, manager.bookings)


class GetSeatAvailabilityTest(unittest.TestCase):
    def test_all_seats_available_initially(self):
        manager = make_manager()
        self.assertEqual(
            [
                SeatAvailability("A", 1, True),
                SeatAvailability("A", 2, True),
                SeatAvailability("B", 1, True),
                SeatAvailability("B", 2, True),
                SeatAvailability("B", 3, True),
            ],
            manager.get_seat_availability("s1"),
        )

    def test_booked_seats_are_unavailable_only_for_their_screening(self):
        manager = make_manager()
        manager.book_seat("s1", "alice", "B", 2)
        unavailable = [(a.row, a.seat) for a in manager.get_seat_availability("s1") if not a.available]
        self.assertEqual([("B", 2)], unavailable)
        self.assertTrue(all(a.available for a in manager.get_seat_availability("s2")))

    def test_rejects_unknown_screening(self):
        manager = make_manager()
        with self.assertLogs("seat_booking", "WARNING"), self.assertRaises(UnknownScreeningError):
            manager.get_seat_availability("nope")


if __name__ == "__main__":
    unittest.main()
