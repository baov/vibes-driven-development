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


def make_service():
    service = BookingService()
    room = Room("Room 1", [("A", 3), ("B", 2)])
    service.add_screening(Screening("s1", room))
    return service


class RoomTest(unittest.TestCase):
    def test_seats_are_listed_in_row_then_number_order(self):
        room = Room("R", [("A", 2), ("B", 1)])
        self.assertEqual(room.seats(), [Seat("A", 1), Seat("A", 2), Seat("B", 1)])

    def test_rejects_duplicate_row_labels(self):
        with self.assertRaises(ValueError):
            Room("R", [("A", 2), ("A", 3)])

    def test_rejects_empty_rows(self):
        with self.assertRaises(ValueError):
            Room("R", [("A", 0)])


class BookingServiceTest(unittest.TestCase):
    def test_all_seats_available_initially(self):
        service = make_service()
        availability = service.availability("s1")
        self.assertEqual(len(availability), 5)
        self.assertTrue(all(availability.values()))

    def test_book_seat_makes_it_unavailable(self):
        service = make_service()
        booking = service.book("s1", "A", 2, "alice")
        self.assertEqual(booking.seat, Seat("A", 2))
        self.assertEqual(booking.client_id, "alice")
        availability = service.availability("s1")
        self.assertFalse(availability[Seat("A", 2)])
        self.assertEqual(sum(not free for free in availability.values()), 1)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = make_service()
        service.book("s1", "B", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", "B", 1, "bob")
        # Same client booking twice is also rejected.
        with self.assertRaises(SeatAlreadyBookedError):
            service.book("s1", "B", 1, "alice")

    def test_bookings_are_per_screening(self):
        service = make_service()
        service.add_screening(Screening("s2", Room("Room 1", [("A", 3), ("B", 2)])))
        service.book("s1", "A", 1, "alice")
        service.book("s2", "A", 1, "bob")
        self.assertTrue(service.availability("s2")[Seat("B", 2)])
        self.assertFalse(service.availability("s2")[Seat("A", 1)])

    def test_nonexistent_seat_is_rejected(self):
        service = make_service()
        for row, number in [("C", 1), ("A", 0), ("A", 4), ("B", 3)]:
            with self.subTest(row=row, number=number):
                with self.assertRaises(InvalidSeatError):
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
        with self.assertRaises(DuplicateScreeningError):
            service.add_screening(Screening("s1", Room("Other", [("A", 1)])))

    def test_concurrent_bookings_of_same_seat_allow_exactly_one(self):
        service = make_service()
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                successes.append(service.book("s1", "A", 1, client))
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
