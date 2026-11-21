import threading
import unittest

from seat_booking import (
    Booking,
    Room,
    Screening,
    ScreeningError,
    SeatAlreadyBookedError,
    SeatBookingManager,
    SeatNotFoundError,
)


def make_manager():
    manager = SeatBookingManager()
    room = Room("Room 1", {"A": 3, "B": 2})
    manager.add_screening(Screening("s1", room))
    return manager


class SeatBookingManagerTest(unittest.TestCase):
    def test_new_screening_has_every_seat_available(self):
        manager = make_manager()
        self.assertEqual(
            manager.get_seat_availability("s1"),
            {"A": {1: True, 2: True, 3: True}, "B": {1: True, 2: True}},
        )

    def test_booking_a_free_seat_returns_the_booking_and_marks_it_unavailable(self):
        manager = make_manager()
        booking = manager.book_seat("s1", "A", 2, "alice")
        self.assertEqual(booking, Booking("s1", "A", 2, "alice"))
        self.assertEqual(
            manager.get_seat_availability("s1"),
            {"A": {1: True, 2: False, 3: True}, "B": {1: True, 2: True}},
        )

    def test_booking_an_already_booked_seat_is_rejected(self):
        manager = make_manager()
        manager.book_seat("s1", "B", 1, "alice")
        with self.assertLogs("seat_booking", level="WARNING"):
            with self.assertRaises(SeatAlreadyBookedError):
                manager.book_seat("s1", "B", 1, "bob")
        # The original booking is untouched and the seat stays unavailable.
        self.assertFalse(manager.get_seat_availability("s1")["B"][1])

    def test_same_client_cannot_book_the_same_seat_twice(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "alice")
        with self.assertLogs("seat_booking", level="WARNING"):
            with self.assertRaises(SeatAlreadyBookedError):
                manager.book_seat("s1", "A", 1, "alice")

    def test_same_seat_can_be_booked_in_different_screenings_of_the_same_room(self):
        manager = make_manager()
        manager.add_screening(Screening("s2", Room("Room 1", {"A": 3, "B": 2})))
        manager.book_seat("s1", "A", 1, "alice")
        manager.book_seat("s2", "A", 1, "bob")
        self.assertFalse(manager.get_seat_availability("s1")["A"][1])
        self.assertFalse(manager.get_seat_availability("s2")["A"][1])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        manager = make_manager()
        for row, seat in [("C", 1), ("A", 0), ("A", 4), ("B", 3)]:
            with self.subTest(row=row, seat=seat):
                with self.assertRaises(SeatNotFoundError):
                    manager.book_seat("s1", row, seat, "alice")
        self.assertTrue(
            all(all(r.values()) for r in manager.get_seat_availability("s1").values())
        )

    def test_unknown_screening_is_rejected(self):
        manager = make_manager()
        with self.assertRaises(ScreeningError):
            manager.book_seat("nope", "A", 1, "alice")
        with self.assertRaises(ScreeningError):
            manager.get_seat_availability("nope")

    def test_adding_a_screening_twice_is_rejected_and_keeps_bookings(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "alice")
        with self.assertRaises(ScreeningError):
            manager.add_screening(Screening("s1", Room("Other", {"Z": 1})))
        self.assertFalse(manager.get_seat_availability("s1")["A"][1])

    def test_concurrent_bookings_of_one_seat_have_exactly_one_winner(self):
        manager = make_manager()
        results = []
        start = threading.Barrier(20)

        def attempt(client):
            start.wait()
            try:
                manager.book_seat("s1", "A", 1, client)
                results.append("ok")
            except SeatAlreadyBookedError:
                results.append("rejected")

        with self.assertLogs("seat_booking", level="WARNING"):
            threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("rejected"), 19)


if __name__ == "__main__":
    unittest.main()
