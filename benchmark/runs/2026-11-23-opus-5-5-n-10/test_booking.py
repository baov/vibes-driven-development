import threading
import unittest

from seat_booking.booking import (
    Booking,
    BookingService,
    Room,
    Screening,
    SeatAlreadyBookedError,
    UnknownScreeningError,
    UnknownSeatError,
)


def make_service():
    service = BookingService()
    room = Room("Room 1", {"A": 3, "B": 2})
    service.add_screening(Screening("s1", room))
    return service


class RoomTest(unittest.TestCase):
    def test_lists_every_seat_in_row_order(self):
        room = Room("R", {"A": 2, "B": 1})
        self.assertEqual(list(room.seats()), [("A", 1), ("A", 2), ("B", 1)])

    def test_rejects_empty_room(self):
        with self.assertRaises(ValueError):
            Room("R", {})

    def test_rejects_row_without_seats(self):
        with self.assertRaises(ValueError):
            Room("R", {"A": 0})

    def test_layout_is_isolated_from_caller_dict(self):
        rows = {"A": 1}
        room = Room("R", rows)
        rows["A"] = 5
        self.assertFalse(room.has_seat("A", 2))


class BookingServiceTest(unittest.TestCase):
    def test_all_seats_available_initially(self):
        service = make_service()
        self.assertEqual(
            service.availability("s1"),
            {("A", 1): True, ("A", 2): True, ("A", 3): True,
             ("B", 1): True, ("B", 2): True},
        )

    def test_booking_a_seat_makes_it_unavailable(self):
        service = make_service()
        booking = service.book_seat("s1", "A", 2, "alice")
        self.assertEqual(booking, Booking("s1", "A", 2, "alice"))
        availability = service.availability("s1")
        self.assertFalse(availability[("A", 2)])
        self.assertEqual(sum(availability.values()), 4)

    def test_booking_an_already_booked_seat_is_rejected(self):
        service = make_service()
        service.book_seat("s1", "A", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book_seat("s1", "A", 1, "bob")
        # The original booking is kept.
        self.assertFalse(service.availability("s1")[("A", 1)])

    def test_same_client_cannot_double_book_a_seat(self):
        service = make_service()
        service.book_seat("s1", "B", 1, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            service.book_seat("s1", "B", 1, "alice")

    def test_bookings_are_per_screening(self):
        service = make_service()
        service.add_screening(Screening("s2", Room("Room 1", {"A": 3, "B": 2})))
        service.book_seat("s1", "A", 1, "alice")
        service.book_seat("s2", "A", 1, "bob")
        self.assertTrue(service.availability("s2")[("A", 2)])
        self.assertFalse(service.availability("s2")[("A", 1)])

    def test_unknown_seat_is_rejected(self):
        service = make_service()
        for row, seat in [("C", 1), ("A", 0), ("A", 4), ("B", 3)]:
            with self.subTest(row=row, seat=seat):
                with self.assertRaises(UnknownSeatError):
                    service.book_seat("s1", row, seat, "alice")
        self.assertTrue(all(service.availability("s1").values()))

    def test_unknown_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(UnknownScreeningError):
            service.book_seat("nope", "A", 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            service.availability("nope")

    def test_duplicate_screening_is_rejected(self):
        service = make_service()
        with self.assertRaises(ValueError):
            service.add_screening(Screening("s1", Room("Other", {"A": 1})))

    def test_concurrent_bookings_of_one_seat_yield_one_winner(self):
        service = make_service()
        successes, failures = [], []
        barrier = threading.Barrier(20)

        def attempt(client):
            barrier.wait()
            try:
                service.book_seat("s1", "A", 1, client)
                successes.append(client)
            except SeatAlreadyBookedError:
                failures.append(client)

        threads = [threading.Thread(target=attempt, args=(f"c{i}",))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 19)


if __name__ == "__main__":
    unittest.main()
