import threading
import unittest

from seat_booking import (
    BookingManager,
    Room,
    Screening,
    SeatAlreadyBookedError,
    UnknownScreeningError,
    UnknownSeatError,
)


def make_service():
    service = BookingManager()
    room = Room("Room 1", {"A": 3, "B": 2})
    service.add_screening(Screening("s1", room))
    service.add_screening(Screening("s2", room))
    return service


class RoomTest(unittest.TestCase):
    def test_rejects_room_without_rows(self):
        with self.assertRaises(ValueError):
            Room("empty", {})

    def test_rejects_row_without_seats(self):
        with self.assertRaises(ValueError):
            Room("bad", {"A": 0})

    def test_has_seat(self):
        room = Room("r", {"A": 2})
        self.assertTrue(room.has_seat("A", 1))
        self.assertTrue(room.has_seat("A", 2))
        self.assertFalse(room.has_seat("A", 0))
        self.assertFalse(room.has_seat("A", 3))
        self.assertFalse(room.has_seat("Z", 1))


class SeatBookingTest(unittest.TestCase):
    def test_all_seats_available_initially(self):
        service = make_service()
        self.assertEqual(
            service.seat_availability("s1"),
            {("A", 1): True, ("A", 2): True, ("A", 3): True, ("B", 1): True, ("B", 2): True},
        )

    def test_booked_seat_becomes_unavailable(self):
        service = make_service()
        service.book_seat("s1", "A", 2, "alice")
        availability = service.seat_availability("s1")
        self.assertFalse(availability[("A", 2)])
        self.assertEqual(sum(availability.values()), 4)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = make_service()
        service.book_seat("s1", "A", 2, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book_seat("s1", "A", 2, "bob")
        # Rejection must not change the existing booking or other seats.
        self.assertEqual(sum(service.seat_availability("s1").values()), 4)

    def test_same_client_cannot_book_same_seat_twice(self):
        service = make_service()
        service.book_seat("s1", "B", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book_seat("s1", "B", 1, "alice")

    def test_bookings_are_per_screening(self):
        service = make_service()
        service.book_seat("s1", "A", 1, "alice")
        service.book_seat("s2", "A", 1, "bob")
        self.assertTrue(all(service.seat_availability("s2")[k] for k in [("A", 2), ("B", 1)]))
        self.assertFalse(service.seat_availability("s2")[("A", 1)])

    def test_unknown_seat_is_rejected(self):
        service = make_service()
        for row, seat in [("A", 4), ("A", 0), ("C", 1)]:
            with self.assertRaises(UnknownSeatError):
                service.book_seat("s1", row, seat, "alice")
        self.assertTrue(all(service.seat_availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(UnknownScreeningError):
            service.book_seat("nope", "A", 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            service.seat_availability("nope")

    def test_duplicate_screening_is_rejected(self):
        service = make_service()
        service.book_seat("s1", "A", 1, "alice")
        with self.assertRaises(ValueError):
            service.add_screening(Screening("s1", Room("Room 2", {"A": 1})))
        self.assertFalse(service.seat_availability("s1")[("A", 1)])

    def test_concurrent_bookings_of_same_seat_only_one_succeeds(self):
        service = make_service()
        successes, rejections = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                service.book_seat("s1", "A", 1, client)
                successes.append(client)
            except SeatAlreadyBookedError:
                rejections.append(client)

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(rejections), 19)


if __name__ == "__main__":
    unittest.main()
