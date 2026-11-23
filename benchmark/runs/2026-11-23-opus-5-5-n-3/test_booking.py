import threading
import unittest

from seat_booking.booking import (
    Booking,
    BookingService,
    DuplicateScreeningError,
    Room,
    Screening,
    Seat,
    SeatAlreadyBookedError,
    UnknownScreeningError,
    UnknownSeatError,
)


class RoomTest(unittest.TestCase):
    def test_seats_are_listed_row_by_row(self):
        room = Room("Small", {"A": 2, "B": 1})
        self.assertEqual(room.seats(), [Seat("A", 1), Seat("A", 2), Seat("B", 1)])

    def test_rejects_empty_room_and_invalid_counts(self):
        for rows in ({}, {"A": 0}, {"A": -1}, {"A": 1.5}, {"A": True}):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                Room("Bad", rows)

    def test_room_is_isolated_from_caller_dict(self):
        rows = {"A": 1}
        room = Room("R", rows)
        rows["B"] = 5
        self.assertEqual(room.seats(), [Seat("A", 1)])


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.room = Room("Room 1", {"A": 3, "B": 2})
        self.service.add_screening(Screening("s1", self.room))
        self.service.add_screening(Screening("s2", self.room))

    def test_book_free_seat(self):
        booking = self.service.book("s1", "alice", "A", 2)
        self.assertEqual(booking, Booking("s1", "alice", Seat("A", 2)))
        self.assertFalse(self.service.availability("s1")[Seat("A", 2)])

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.service.book("s1", "alice", "A", 2)
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "bob", "A", 2)
        # The original booking is kept.
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", "alice", "A", 2)

    def test_same_seat_can_be_booked_for_another_screening(self):
        self.service.book("s1", "alice", "A", 1)
        self.service.book("s2", "bob", "A", 1)
        self.assertFalse(self.service.availability("s2")[Seat("A", 1)])

    def test_availability_lists_every_seat(self):
        self.service.book("s1", "alice", "B", 1)
        self.assertEqual(
            list(self.service.availability("s1").items()),
            [
                (Seat("A", 1), True),
                (Seat("A", 2), True),
                (Seat("A", 3), True),
                (Seat("B", 1), False),
                (Seat("B", 2), True),
            ],
        )

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        for row, number in (("C", 1), ("A", 0), ("A", 4), ("B", 3)):
            with self.subTest(row=row, number=number), self.assertRaises(UnknownSeatError):
                self.service.book("s1", "alice", row, number)
        self.assertTrue(all(self.service.availability("s1").values()))

    def test_unknown_screening(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", "alice", "A", 1)
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")

    def test_duplicate_screening_is_rejected(self):
        with self.assertRaises(DuplicateScreeningError):
            self.service.add_screening(Screening("s1", self.room))

    def test_concurrent_bookings_of_one_seat_succeed_once(self):
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                successes.append(self.service.book("s1", client, "A", 1))
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
