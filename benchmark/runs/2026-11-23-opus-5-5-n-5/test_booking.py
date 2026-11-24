import threading
import unittest

from seat_booking import (
    Booking,
    BookingManager,
    InvalidSeatError,
    Room,
    Screening,
    SeatAlreadyBookedError,
    UnknownScreeningError,
)


def make_manager():
    manager = BookingManager()
    manager.add_screening(Screening("s1", Room.rectangular("Room A", rows=2, seats_per_row=3)))
    return manager


class RoomTest(unittest.TestCase):
    def test_seats_lists_every_seat_of_irregular_room(self):
        room = Room("Odd", [2, 1])
        self.assertEqual(list(room.seats()), [(1, 1), (1, 2), (2, 1)])

    def test_has_seat_bounds(self):
        room = Room.rectangular("A", rows=2, seats_per_row=3)
        self.assertTrue(room.has_seat(1, 1))
        self.assertTrue(room.has_seat(2, 3))
        for row, seat in [(0, 1), (3, 1), (1, 0), (1, 4), ("1", 1), (1, 1.0)]:
            self.assertFalse(room.has_seat(row, seat), (row, seat))

    def test_invalid_room_rejected(self):
        for rows in ([], [3, 0], [-1], [2.5]):
            with self.assertRaises(ValueError):
                Room("Bad", rows)


class BookingTest(unittest.TestCase):
    def test_book_free_seat(self):
        manager = make_manager()
        booking = manager.book("s1", 1, 2, "alice")
        self.assertEqual(booking, Booking("s1", 1, 2, "alice"))

    def test_booking_already_booked_seat_is_rejected(self):
        manager = make_manager()
        manager.book("s1", 1, 2, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book("s1", 1, 2, "bob")
        # Same client booking twice is rejected too.
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book("s1", 1, 2, "alice")

    def test_same_seat_in_different_screenings_is_independent(self):
        manager = make_manager()
        manager.add_screening(Screening("s2", Room.rectangular("Room A", rows=2, seats_per_row=3)))
        manager.book("s1", 1, 1, "alice")
        manager.book("s2", 1, 1, "bob")
        self.assertFalse(manager.availability("s2")[(1, 1)])

    def test_nonexistent_seat_is_rejected(self):
        manager = make_manager()
        for row, seat in [(0, 1), (3, 1), (1, 4)]:
            with self.assertRaises(InvalidSeatError):
                manager.book("s1", row, seat, "alice")
        self.assertTrue(all(manager.availability("s1").values()))

    def test_unknown_screening(self):
        manager = make_manager()
        with self.assertRaises(UnknownScreeningError):
            manager.book("nope", 1, 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            manager.availability("nope")

    def test_duplicate_screening_id_rejected(self):
        manager = make_manager()
        with self.assertRaises(ValueError):
            manager.add_screening(Screening("s1", Room.rectangular("B", 1, 1)))

    def test_availability_reports_every_seat(self):
        manager = make_manager()
        manager.book("s1", 2, 3, "alice")
        availability = manager.availability("s1")
        self.assertEqual(len(availability), 6)
        self.assertEqual(
            {pos for pos, free in availability.items() if not free}, {(2, 3)}
        )

    def test_availability_is_a_snapshot(self):
        manager = make_manager()
        availability = manager.availability("s1")
        availability[(1, 1)] = False
        self.assertTrue(manager.availability("s1")[(1, 1)])

    def test_concurrent_bookings_of_same_seat_only_one_wins(self):
        manager = make_manager()
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                successes.append(manager.book("s1", 1, 1, client))
            except SeatAlreadyBookedError:
                failures.append(client)

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 19)


if __name__ == "__main__":
    unittest.main()
