import threading
import unittest

from seat_booking.booking import (
    Room,
    SeatAlreadyBookedError,
    SeatAvailability,
    SeatBookingManager,
    SeatNotFoundError,
    UnknownRoomError,
    UnknownScreeningError,
)


class SeatBookingTest(unittest.TestCase):
    def setUp(self):
        self.service = SeatBookingManager()
        self.service.add_room(Room("room-1", rows=2, seats_per_row=3))
        self.service.add_screening("s1", "room-1")

    def available_seats(self, screening_id):
        return {
            (s.row, s.seat) for s in self.service.seat_availability(screening_id) if s.available
        }

    def test_all_seats_are_available_before_any_booking(self):
        availability = self.service.seat_availability("s1")
        self.assertEqual(
            [(s.row, s.seat) for s in availability],
            [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)],
        )
        self.assertTrue(all(s.available for s in availability))

    def test_booked_seat_becomes_unavailable_and_others_stay_free(self):
        self.service.book_seat("s1", 2, 3, client_id="alice")
        availability = self.service.seat_availability("s1")
        self.assertIn(SeatAvailability(2, 3, False), availability)
        self.assertEqual(len(self.available_seats("s1")), 5)

    def test_booking_an_already_booked_seat_is_rejected(self):
        self.service.book_seat("s1", 1, 1, client_id="alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", 1, 1, client_id="bob")

    def test_same_client_cannot_book_the_same_seat_twice(self):
        self.service.book_seat("s1", 1, 1, client_id="alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book_seat("s1", 1, 1, client_id="alice")

    def test_same_seat_can_be_booked_in_another_screening_of_the_same_room(self):
        self.service.add_screening("s2", "room-1")
        self.service.book_seat("s1", 1, 1, client_id="alice")
        self.service.book_seat("s2", 1, 1, client_id="bob")
        self.assertNotIn((1, 1), self.available_seats("s2"))

    def test_booking_a_seat_outside_the_room_is_rejected(self):
        for row, seat in [(0, 1), (3, 1), (1, 0), (1, 4)]:
            with self.subTest(row=row, seat=seat):
                with self.assertRaises(SeatNotFoundError):
                    self.service.book_seat("s1", row, seat, client_id="alice")
        self.assertEqual(len(self.available_seats("s1")), 6)

    def test_unknown_screening_is_rejected(self):
        with self.assertRaises(UnknownScreeningError):
            self.service.book_seat("nope", 1, 1, client_id="alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.seat_availability("nope")

    def test_screening_in_unknown_room_is_rejected(self):
        with self.assertRaises(UnknownRoomError):
            self.service.add_screening("s2", "no-such-room")

    def test_duplicate_screening_is_rejected(self):
        self.service.book_seat("s1", 1, 1, client_id="alice")
        with self.assertRaises(ValueError):
            self.service.add_screening("s1", "room-1")
        # existing bookings must survive the rejected re-registration
        self.assertNotIn((1, 1), self.available_seats("s1"))

    def test_room_must_have_seats(self):
        with self.assertRaises(ValueError):
            Room("empty", rows=0, seats_per_row=5)
        with self.assertRaises(ValueError):
            Room("empty", rows=5, seats_per_row=0)

    def test_concurrent_bookings_of_one_seat_have_exactly_one_winner(self):
        winners, losers = [], []
        start = threading.Barrier(20)

        def attempt(client):
            start.wait()
            try:
                self.service.book_seat("s1", 1, 2, client_id=client)
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
