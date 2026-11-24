import threading
import unittest

from seat_booking import (
    Room,
    Screening,
    SeatAlreadyBookedError,
    SeatBookingManager,
    UnknownScreeningError,
    UnknownSeatError,
)


def make_manager():
    # Room with two rows: A has 3 seats, B has 2 seats
    room = Room("Room 1", {"A": 3, "B": 2})
    manager = SeatBookingManager()
    manager.add_screening(Screening("s1", room))
    return manager


class RoomTest(unittest.TestCase):
    def test_has_seat_only_for_seats_in_the_layout(self):
        room = Room("Room 1", {"A": 3})
        self.assertTrue(room.has_seat("A", 1))
        self.assertTrue(room.has_seat("A", 3))
        self.assertFalse(room.has_seat("A", 0))
        self.assertFalse(room.has_seat("A", 4))
        self.assertFalse(room.has_seat("Z", 1))

    def test_rejects_room_without_rows(self):
        with self.assertRaises(ValueError):
            Room("Empty", {})

    def test_rejects_row_without_seats(self):
        with self.assertRaises(ValueError):
            Room("Broken", {"A": 0})

    def test_layout_is_copied(self):
        rows = {"A": 2}
        room = Room("Room 1", rows)
        rows["A"] = 10
        self.assertFalse(room.has_seat("A", 3))


class SeatBookingManagerTest(unittest.TestCase):
    def test_all_seats_available_for_new_screening(self):
        availability = make_manager().get_seat_availability("s1")
        self.assertEqual(
            availability,
            [
                {"row": "A", "seat": 1, "available": True},
                {"row": "A", "seat": 2, "available": True},
                {"row": "A", "seat": 3, "available": True},
                {"row": "B", "seat": 1, "available": True},
                {"row": "B", "seat": 2, "available": True},
            ],
        )

    def test_booked_seat_becomes_unavailable(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 2, "client-1")
        unavailable = [
            (s["row"], s["seat"]) for s in manager.get_seat_availability("s1") if not s["available"]
        ]
        self.assertEqual(unavailable, [("A", 2)])

    def test_booking_an_already_booked_seat_is_rejected(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "client-1")
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "A", 1, "client-2")

    def test_same_client_cannot_book_the_same_seat_twice(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "client-1")
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "A", 1, "client-1")

    def test_same_seat_can_be_booked_in_different_screenings(self):
        room = Room("Room 1", {"A": 1})
        manager = SeatBookingManager()
        manager.add_screening(Screening("s1", room))
        manager.add_screening(Screening("s2", room))
        manager.book_seat("s1", "A", 1, "client-1")
        manager.book_seat("s2", "A", 1, "client-2")
        self.assertFalse(manager.get_seat_availability("s1")[0]["available"])
        self.assertFalse(manager.get_seat_availability("s2")[0]["available"])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        manager = make_manager()
        with self.assertRaises(UnknownSeatError):
            manager.book_seat("s1", "B", 3, "client-1")
        with self.assertRaises(UnknownSeatError):
            manager.book_seat("s1", "C", 1, "client-1")

    def test_unknown_screening_is_rejected(self):
        manager = make_manager()
        with self.assertRaises(UnknownScreeningError):
            manager.book_seat("nope", "A", 1, "client-1")
        with self.assertRaises(UnknownScreeningError):
            manager.get_seat_availability("nope")

    def test_registering_a_screening_twice_is_rejected_and_keeps_bookings(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "client-1")
        with self.assertRaises(ValueError):
            manager.add_screening(Screening("s1", Room("Other", {"A": 1})))
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "A", 1, "client-2")

    def test_concurrent_bookings_of_one_seat_have_a_single_winner(self):
        manager = make_manager()
        successes = []
        rejections = []

        def attempt(client_id):
            try:
                manager.book_seat("s1", "A", 1, client_id)
                successes.append(client_id)
            except SeatAlreadyBookedError:
                rejections.append(client_id)

        threads = [threading.Thread(target=attempt, args=(f"client-{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(rejections), 19)


if __name__ == "__main__":
    unittest.main()
