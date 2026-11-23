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
        availability = self.service.seat_availability("s1")
        self.assertEqual(
            list(availability),
            [Seat("A", 1), Seat("A", 2), Seat("A", 3), Seat("B", 1), Seat("B", 2)],
        )
        self.assertTrue(all(availability.values()))

    def test_booking_a_seat_makes_it_unavailable(self):
        booking = self.service.book_seat("s1", Seat("A", 2), "alice")

        self.assertEqual(booking.client_id, "alice")
        self.assertEqual(booking.seat, Seat("A", 2))
        availability = self.service.seat_availability("s1")
        self.assertFalse(availability[Seat("A", 2)])
        self.assertEqual(sum(availability.values()), 4)

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.service.book_seat("s1", Seat("A", 1), "alice")

        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", Seat("A", 1), "bob")
        # The original booking is kept.
        self.assertFalse(self.service.seat_availability("s1")[Seat("A", 1)])

    def test_same_client_cannot_book_the_same_seat_twice(self):
        self.service.book_seat("s1", Seat("A", 1), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", Seat("A", 1), "alice")

    def test_same_seat_can_be_booked_for_different_screenings(self):
        self.service.add_screening(Screening("s2", self.room))
        self.service.book_seat("s1", Seat("A", 1), "alice")

        self.service.book_seat("s2", Seat("A", 1), "bob")

        self.assertFalse(self.service.seat_availability("s2")[Seat("A", 1)])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        for seat in (Seat("C", 1), Seat("B", 3), Seat("A", 0)):
            with self.subTest(seat=seat):
                with self.assertRaises(UnknownSeatError):
                    self.service.book_seat("s1", seat, "alice")
        self.assertTrue(all(self.service.seat_availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book_seat("nope", Seat("A", 1), "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.seat_availability("nope")

    def test_concurrent_bookings_of_same_seat_allow_exactly_one(self):
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                successes.append(self.service.book_seat("s1", Seat("B", 1), client))
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
