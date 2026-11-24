import threading
import unittest

from seat_booking.booking import (
    BookingService,
    Room,
    Screening,
    Seat,
    SeatAlreadyBookedError,
    SeatAvailability,
    UnknownScreeningError,
    UnknownSeatError,
)


def make_service():
    room = Room("Room 1", {"A": 3, "B": 2})
    service = BookingService()
    service.add_screening(Screening("s1", room))
    return service


class BookingTest(unittest.TestCase):
    def test_new_screening_has_every_seat_available(self):
        service = make_service()
        self.assertEqual(
            service.availability("s1"),
            [
                SeatAvailability(Seat("A", 1), True),
                SeatAvailability(Seat("A", 2), True),
                SeatAvailability(Seat("A", 3), True),
                SeatAvailability(Seat("B", 1), True),
                SeatAvailability(Seat("B", 2), True),
            ],
        )

    def test_booked_seat_becomes_unavailable(self):
        service = make_service()
        service.book("s1", Seat("A", 2), "alice")
        unavailable = [a.seat for a in service.availability("s1") if not a.available]
        self.assertEqual(unavailable, [Seat("A", 2)])

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = make_service()
        service.book("s1", Seat("B", 1), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", Seat("B", 1), "bob")

    def test_same_client_cannot_book_the_same_seat_twice(self):
        service = make_service()
        service.book("s1", Seat("B", 1), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", Seat("B", 1), "alice")

    def test_bookings_are_independent_between_screenings(self):
        room = Room("Room 1", {"A": 1})
        service = BookingService()
        service.add_screening(Screening("s1", room))
        service.add_screening(Screening("s2", room))
        service.book("s1", Seat("A", 1), "alice")
        service.book("s2", Seat("A", 1), "bob")
        self.assertFalse(service.availability("s1")[0].available)
        self.assertFalse(service.availability("s2")[0].available)

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        service = make_service()
        for seat in (Seat("C", 1), Seat("A", 0), Seat("A", 4), Seat("B", 3)):
            with self.subTest(seat=seat):
                with self.assertRaises(UnknownSeatError):
                    service.book("s1", seat, "alice")
        self.assertTrue(all(a.available for a in service.availability("s1")))

    def test_unknown_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(UnknownScreeningError):
            service.book("nope", Seat("A", 1), "alice")
        with self.assertRaises(UnknownScreeningError):
            service.availability("nope")

    def test_duplicate_screening_id_is_rejected(self):
        service = make_service()
        with self.assertRaises(ValueError):
            service.add_screening(Screening("s1", Room("Other", {"A": 1})))

    def test_room_must_have_rows_with_seats(self):
        with self.assertRaises(ValueError):
            Room("Empty", {})
        with self.assertRaises(ValueError):
            Room("Bad", {"A": 0})

    def test_concurrent_bookings_of_one_seat_yield_a_single_winner(self):
        service = make_service()
        successes = []
        failures = []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                service.book("s1", Seat("A", 1), client)
                successes.append(client)
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
