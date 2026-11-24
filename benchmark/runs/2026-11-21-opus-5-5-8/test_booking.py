import threading
import unittest

from seat_booking.booking import (
    BookingManager,
    DuplicateScreeningError,
    Room,
    Screening,
    SeatAlreadyBookedError,
    UnknownScreeningError,
    UnknownSeatError,
)


def make_manager():
    room = Room("Room 1", (("A", 2), ("B", 3)))
    manager = BookingManager()
    manager.add_screening(Screening("s1", room))
    return manager


class RoomTest(unittest.TestCase):
    def test_lists_every_seat_in_room_order(self):
        room = Room("Room 1", (("A", 2), ("B", 1)))
        self.assertEqual(room.seats(), [("A", 1), ("A", 2), ("B", 1)])

    def test_rejects_duplicate_row_labels(self):
        with self.assertRaises(ValueError):
            Room("Room 1", (("A", 2), ("A", 3)))

    def test_rejects_empty_row(self):
        with self.assertRaises(ValueError):
            Room("Room 1", (("A", 0),))


class BookSeatTest(unittest.TestCase):
    def test_booking_a_free_seat_makes_it_unavailable(self):
        manager = make_manager()
        manager.book_seat("s1", "B", 2, client_id="alice")
        availability = manager.seat_availability("s1")
        self.assertFalse(availability[("B", 2)])
        self.assertTrue(availability[("B", 1)])

    def test_booking_an_already_booked_seat_is_rejected(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, client_id="alice")
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "A", 1, client_id="bob")

    def test_same_seat_can_be_booked_in_different_screenings(self):
        manager = make_manager()
        manager.add_screening(Screening("s2", Room("Room 1", (("A", 2),))))
        manager.book_seat("s1", "A", 1, client_id="alice")
        manager.book_seat("s2", "A", 1, client_id="bob")
        self.assertFalse(manager.seat_availability("s2")[("A", 1)])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        manager = make_manager()
        for row, number in (("A", 3), ("A", 0), ("C", 1)):
            with self.subTest(row=row, number=number):
                with self.assertRaises(UnknownSeatError):
                    manager.book_seat("s1", row, number, client_id="alice")
        self.assertTrue(all(manager.seat_availability("s1").values()))

    def test_booking_for_an_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            make_manager().book_seat("nope", "A", 1, client_id="alice")

    def test_concurrent_bookings_of_one_seat_let_exactly_one_succeed(self):
        manager = make_manager()
        outcomes = []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                manager.book_seat("s1", "A", 1, client_id=client)
                outcomes.append("ok")
            except SeatAlreadyBookedError:
                outcomes.append("rejected")

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 19)


class SeatAvailabilityTest(unittest.TestCase):
    def test_every_seat_is_available_for_a_new_screening(self):
        availability = make_manager().seat_availability("s1")
        self.assertEqual(
            availability,
            {("A", 1): True, ("A", 2): True, ("B", 1): True, ("B", 2): True, ("B", 3): True},
        )

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            make_manager().seat_availability("nope")


class AddScreeningTest(unittest.TestCase):
    def test_duplicate_screening_id_is_rejected(self):
        manager = make_manager()
        with self.assertRaises(DuplicateScreeningError):
            manager.add_screening(Screening("s1", Room("Room 2", (("A", 1),))))


if __name__ == "__main__":
    unittest.main()
