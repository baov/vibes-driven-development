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


def make_service():
    service = BookingService()
    room = Room("Room 1", {"A": 3, "B": 2})
    service.add_screening(Screening("s1", room))
    service.add_screening(Screening("s2", room))
    return service


class BookSeatTest(unittest.TestCase):
    def test_client_can_book_a_free_seat(self):
        service = make_service()
        booking = service.book("s1", Seat("A", 2), "alice")
        self.assertEqual(booking.seat, Seat("A", 2))
        self.assertEqual(booking.client_id, "alice")
        self.assertEqual(booking.screening_id, "s1")

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = make_service()
        service.book("s1", Seat("A", 2), "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", Seat("A", 2), "bob")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", Seat("A", 2), "alice")

    def test_same_seat_can_be_booked_for_different_screenings(self):
        service = make_service()
        service.book("s1", Seat("A", 1), "alice")
        service.book("s2", Seat("A", 1), "bob")
        self.assertFalse(service.availability("s2")[Seat("A", 1)])

    def test_seat_outside_room_is_rejected(self):
        service = make_service()
        for seat in (Seat("A", 0), Seat("A", 4), Seat("C", 1)):
            with self.subTest(seat=seat), self.assertRaises(UnknownSeatError):
                service.book("s1", seat, "alice")

    def test_unknown_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(UnknownScreeningError):
            service.book("nope", Seat("A", 1), "alice")
        with self.assertRaises(UnknownScreeningError):
            service.availability("nope")

    def test_concurrent_bookings_of_same_seat_yield_exactly_one_success(self):
        service = make_service()
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                successes.append(service.book("s1", Seat("B", 1), client))
            except SeatAlreadyBookedError:
                failures.append(client)

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 19)


class AvailabilityTest(unittest.TestCase):
    def test_lists_every_seat_of_the_room_as_available_initially(self):
        service = make_service()
        self.assertEqual(
            service.availability("s1"),
            {
                Seat("A", 1): True, Seat("A", 2): True, Seat("A", 3): True,
                Seat("B", 1): True, Seat("B", 2): True,
            },
        )

    def test_booked_seat_is_reported_unavailable(self):
        service = make_service()
        service.book("s1", Seat("B", 2), "alice")
        availability = service.availability("s1")
        self.assertFalse(availability[Seat("B", 2)])
        self.assertEqual(sum(availability.values()), 4)
        self.assertTrue(all(service.availability("s2").values()))


class SetupValidationTest(unittest.TestCase):
    def test_room_rejects_invalid_layouts(self):
        for layout in ({}, {"A": 0}, {"A": -1}, {"A": "3"}):
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                Room("bad", layout)

    def test_duplicate_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(ValueError):
            service.add_screening(Screening("s1", Room("Room 2", {"A": 1})))


if __name__ == "__main__":
    unittest.main()
