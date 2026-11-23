import threading
import unittest

from seat_booking import (
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


class BookingTest(unittest.TestCase):
    def test_all_seats_available_before_any_booking(self):
        service = make_service()
        self.assertEqual(
            service.availability("s1"),
            {
                Seat("A", 1): True,
                Seat("A", 2): True,
                Seat("A", 3): True,
                Seat("B", 1): True,
                Seat("B", 2): True,
            },
        )

    def test_booked_seat_becomes_unavailable(self):
        service = make_service()
        self.assertEqual(service.book("s1", "A", 2, "alice"), Seat("A", 2))
        availability = service.availability("s1")
        self.assertFalse(availability[Seat("A", 2)])
        self.assertEqual(sum(availability.values()), 4)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = make_service()
        service.book("s1", "A", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", "A", 1, "bob")
        # The first booking is kept.
        self.assertFalse(service.availability("s1")[Seat("A", 1)])

    def test_same_seat_can_be_booked_for_different_screenings(self):
        service = make_service()
        service.book("s1", "A", 1, "alice")
        service.book("s2", "A", 1, "bob")
        self.assertTrue(service.availability("s2")[Seat("A", 2)])
        self.assertFalse(service.availability("s2")[Seat("A", 1)])

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        service = make_service()
        for row, number in [("C", 1), ("B", 3), ("A", 0)]:
            with self.subTest(row=row, number=number):
                with self.assertRaises(UnknownSeatError):
                    service.book("s1", row, number, "alice")
        self.assertTrue(all(service.availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(UnknownScreeningError):
            service.book("nope", "A", 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            service.availability("nope")

    def test_duplicate_screening_id_is_rejected(self):
        service = make_service()
        with self.assertRaises(ValueError):
            service.add_screening(Screening("s1", Room("Room 2", {"A": 1})))

    def test_invalid_room_is_rejected(self):
        with self.assertRaises(ValueError):
            Room("Empty", {})
        with self.assertRaises(ValueError):
            Room("Bad row", {"A": 0})

    def test_concurrent_bookings_of_one_seat_yield_a_single_winner(self):
        service = make_service()
        successes = []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                service.book("s1", "B", 2, client)
                successes.append(client)
            except SeatAlreadyBookedError:
                pass

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)


if __name__ == "__main__":
    unittest.main()
