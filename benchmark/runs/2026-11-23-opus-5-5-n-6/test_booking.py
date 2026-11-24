import threading
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
        self.room = Room("Room 1", {"A": 3, "B": 2})
        self.service = BookingService()
        self.service.add_screening(Screening("s1", self.room))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(
            set(availability),
            {Seat("A", 1), Seat("A", 2), Seat("A", 3), Seat("B", 1), Seat("B", 2)},
        )
        self.assertTrue(all(availability.values()))

    def test_booking_a_free_seat_marks_it_unavailable(self):
        booking = self.service.book("s1", Seat("A", 2), "alice")
        self.assertEqual(booking.seat, Seat("A", 2))
        self.assertEqual(booking.client_id, "alice")
        availability = self.service.availability("s1")
        self.assertFalse(availability[Seat("A", 2)])
        self.assertEqual(sum(availability.values()), 4)

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.service.book("s1", Seat("A", 1), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", Seat("A", 1), "bob")
        # The original booking is untouched.
        self.assertFalse(self.service.availability("s1")[Seat("A", 1)])

    def test_same_client_cannot_book_same_seat_twice(self):
        self.service.book("s1", Seat("A", 1), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", Seat("A", 1), "alice")

    def test_bookings_are_per_screening(self):
        self.service.add_screening(Screening("s2", self.room))
        self.service.book("s1", Seat("B", 1), "alice")
        self.service.book("s2", Seat("B", 1), "bob")
        self.assertTrue(all(v for s, v in self.service.availability("s2").items() if s != Seat("B", 1)))

    def test_booking_nonexistent_seat_is_rejected(self):
        for seat in (Seat("A", 0), Seat("A", 4), Seat("Z", 1)):
            with self.assertRaises(UnknownSeatError):
                self.service.book("s1", seat, "alice")

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", Seat("A", 1), "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.add_screening(Screening("s1", self.room))

    def test_concurrent_bookings_of_same_seat_allow_exactly_one(self):
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                successes.append(self.service.book("s1", Seat("A", 1), client))
            except SeatAlreadyBookedError:
                failures.append(client)

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 19)


class RoomTest(unittest.TestCase):
    def test_invalid_layouts_are_rejected(self):
        with self.assertRaises(ValueError):
            Room("empty", {})
        with self.assertRaises(ValueError):
            Room("bad", {"A": 0})

    def test_layout_is_copied(self):
        layout = {"A": 2}
        room = Room("r", layout)
        layout["A"] = 10
        self.assertEqual(len(room.seats()), 2)


if __name__ == "__main__":
    unittest.main()
