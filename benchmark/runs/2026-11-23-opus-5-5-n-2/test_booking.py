import threading
import unittest

from seat_booking.booking import (
    BookingService,
    DuplicateScreeningError,
    InvalidSeatError,
    Room,
    Screening,
    Seat,
    SeatAlreadyBookedError,
    UnknownScreeningError,
)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.room = Room("Room 1", rows=3, seats_per_row=4)
        self.service.add_screening(Screening("s1", self.room))

    def test_all_seats_are_available_before_any_booking(self):
        availability = self.service.seat_availability("s1")
        self.assertEqual(len(availability), 12)
        self.assertTrue(all(availability.values()))

    def test_availability_lists_seats_by_row_then_number(self):
        seats = list(self.service.seat_availability("s1"))
        self.assertEqual(seats[0], Seat(1, 1))
        self.assertEqual(seats[3], Seat(1, 4))
        self.assertEqual(seats[4], Seat(2, 1))
        self.assertEqual(seats[-1], Seat(3, 4))

    def test_booking_a_free_seat_succeeds(self):
        booking = self.service.book_seat("s1", 2, 3, "alice")
        self.assertEqual(booking.seat, Seat(2, 3))
        self.assertEqual(booking.client, "alice")
        self.assertEqual(booking.screening_id, "s1")

    def test_booked_seat_shows_as_unavailable_and_others_stay_free(self):
        self.service.book_seat("s1", 2, 3, "alice")
        availability = self.service.seat_availability("s1")
        self.assertFalse(availability[Seat(2, 3)])
        self.assertEqual(sum(availability.values()), 11)

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.service.book_seat("s1", 2, 3, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", 2, 3, "bob")

    def test_same_client_cannot_book_the_same_seat_twice(self):
        self.service.book_seat("s1", 1, 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", 1, 1, "alice")

    def test_rejected_booking_keeps_the_original_booking(self):
        self.service.book_seat("s1", 2, 3, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", 2, 3, "bob")
        self.assertEqual(sum(self.service.seat_availability("s1").values()), 11)

    def test_same_seat_can_be_booked_for_different_screenings_of_a_room(self):
        self.service.add_screening(Screening("s2", self.room))
        self.service.book_seat("s1", 1, 1, "alice")
        self.service.book_seat("s2", 1, 1, "bob")
        self.assertTrue(self.service.seat_availability("s2")[Seat(1, 2)])
        self.assertFalse(self.service.seat_availability("s2")[Seat(1, 1)])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        for row, number in [(0, 1), (4, 1), (1, 0), (1, 5), (-1, -1)]:
            with self.subTest(row=row, number=number):
                with self.assertRaises(InvalidSeatError):
                    self.service.book_seat("s1", row, number, "alice")
        self.assertTrue(all(self.service.seat_availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book_seat("nope", 1, 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.seat_availability("nope")

    def test_adding_a_screening_twice_is_rejected(self):
        with self.assertRaises(DuplicateScreeningError):
            self.service.add_screening(Screening("s1", self.room))

    def test_room_needs_at_least_one_seat(self):
        with self.assertRaises(ValueError):
            Room("Empty", rows=0, seats_per_row=10)
        with self.assertRaises(ValueError):
            Room("Empty", rows=10, seats_per_row=0)

    def test_concurrent_bookings_of_one_seat_yield_a_single_winner(self):
        winners, losers = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                self.service.book_seat("s1", 1, 1, client)
                winners.append(client)
            except SeatAlreadyBookedError:
                losers.append(client)

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 19)


if __name__ == "__main__":
    unittest.main()
