import threading
import unittest

from seat_booking.booking import (
    BookingError,
    BookingManager,
    DuplicateScreeningError,
    InvalidSeatError,
    Room,
    Screening,
    SeatAlreadyBookedError,
    SeatAvailability,
    UnknownScreeningError,
)


def make_manager():
    manager = BookingManager()
    room = Room("room-1", {"A": 2, "B": 3})
    manager.add_screening(Screening("s1", room))
    manager.add_screening(Screening("s2", room))
    return manager


class BookingTest(unittest.TestCase):
    def test_client_can_book_a_free_seat(self):
        manager = make_manager()
        booking = manager.book_seat("s1", "B", 2, "alice")
        self.assertEqual(booking.client_id, "alice")
        self.assertEqual((booking.screening_id, booking.row, booking.seat), ("s1", "B", 2))

    def test_booking_an_already_booked_seat_is_rejected(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "A", 1, "bob")
        # The original booking is untouched.
        self.assertFalse(manager.seat_availability("s1")[0].available)

    def test_same_client_cannot_book_the_same_seat_twice(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            manager.book_seat("s1", "A", 1, "alice")

    def test_same_seat_can_be_booked_for_another_screening(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 1, "alice")
        manager.book_seat("s2", "A", 1, "bob")
        self.assertFalse(manager.seat_availability("s2")[0].available)

    def test_availability_lists_every_seat_in_order(self):
        manager = make_manager()
        manager.book_seat("s1", "A", 2, "alice")
        manager.book_seat("s1", "B", 3, "bob")
        self.assertEqual(
            manager.seat_availability("s1"),
            [
                SeatAvailability("A", 1, True),
                SeatAvailability("A", 2, False),
                SeatAvailability("B", 1, True),
                SeatAvailability("B", 2, True),
                SeatAvailability("B", 3, False),
            ],
        )

    def test_availability_of_a_fresh_screening_is_all_free(self):
        manager = make_manager()
        seats = manager.seat_availability("s2")
        self.assertEqual(len(seats), 5)
        self.assertTrue(all(s.available for s in seats))

    def test_seats_outside_the_room_are_rejected(self):
        manager = make_manager()
        for row, seat in [("C", 1), ("A", 0), ("A", 3), ("B", -1), ("A", "1")]:
            with self.subTest(row=row, seat=seat):
                with self.assertRaises(InvalidSeatError):
                    manager.book_seat("s1", row, seat, "alice")

    def test_unknown_screening_is_rejected(self):
        manager = make_manager()
        with self.assertRaises(UnknownScreeningError):
            manager.book_seat("nope", "A", 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            manager.seat_availability("nope")

    def test_duplicate_screening_is_rejected(self):
        manager = make_manager()
        with self.assertRaises(DuplicateScreeningError):
            manager.add_screening(Screening("s1", Room("room-2", {"A": 1})))

    def test_all_rejections_share_a_base_class(self):
        for error in (UnknownScreeningError, DuplicateScreeningError,
                      InvalidSeatError, SeatAlreadyBookedError):
            self.assertTrue(issubclass(error, BookingError))

    def test_concurrent_bookings_of_one_seat_yield_exactly_one_winner(self):
        manager = make_manager()
        results = []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                manager.book_seat("s1", "A", 1, client)
                results.append("ok")
            except SeatAlreadyBookedError:
                results.append("rejected")

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("rejected"), 19)


class RoomTest(unittest.TestCase):
    def test_room_requires_rows(self):
        with self.assertRaises(ValueError):
            Room("r", {})

    def test_row_requires_a_positive_seat_count(self):
        for count in (0, -2, 1.5):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    Room("r", {"A": count})

    def test_room_is_insulated_from_caller_mutation(self):
        rows = {"A": 2}
        room = Room("r", rows)
        rows["A"] = 50
        self.assertFalse(room.has_seat("A", 3))


if __name__ == "__main__":
    unittest.main()
