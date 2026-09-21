"""Tests for seat_booking.booking.

One test file for the one module under test. The manager is exercised with
real rooms and real screenings rather than mocks: the rules this feature has to
guarantee -- a booked seat is never handed out twice, availability reports
every seat of the room -- only show up in the observable result.
"""

import unittest

from seat_booking.booking import (
    NoSuchSeatError,
    SeatAlreadyBookedError,
    SeatBookingManager,
    UnknownRoomError,
    UnknownScreeningError,
)


class SeatBookingManagerTest(unittest.TestCase):
    def setUp(self):
        # A 3 x 4 room with one screening in it, used by most tests below.
        self.manager = SeatBookingManager()
        self.manager.register_room("room-1", row_count=3, seats_per_row=4)
        self.manager.schedule_screening("screening-1", "room-1")

    def test_books_a_free_seat(self):
        booking = self.manager.book_seat("screening-1", 2, 3, "alice")

        self.assertEqual(
            {
                "screening_id": "screening-1",
                "row": 2,
                "number": 3,
                "client_id": "alice",
            },
            booking,
        )

    def test_booked_seat_is_no_longer_available(self):
        self.manager.book_seat("screening-1", 2, 3, "alice")

        seats = self.manager.availability("screening-1")

        booked = [seat for seat in seats if not seat["available"]]
        self.assertEqual(
            [{"row": 2, "number": 3, "available": False, "client_id": "alice"}],
            booked,
        )

    def test_rejects_a_seat_booked_by_another_client(self):
        self.manager.book_seat("screening-1", 2, 3, "alice")

        with self.assertRaises(SeatAlreadyBookedError) as caught:
            self.manager.book_seat("screening-1", 2, 3, "bob")

        # The rejection names the client that actually holds the seat.
        self.assertEqual("alice", caught.exception.client_id)
        self.assertEqual(2, caught.exception.row)
        self.assertEqual(3, caught.exception.number)

    def test_rejects_a_seat_the_same_client_already_booked(self):
        self.manager.book_seat("screening-1", 1, 1, "alice")

        with self.assertRaises(SeatAlreadyBookedError):
            self.manager.book_seat("screening-1", 1, 1, "alice")

    def test_rejected_booking_leaves_the_seat_to_its_holder(self):
        self.manager.book_seat("screening-1", 2, 3, "alice")

        with self.assertRaises(SeatAlreadyBookedError):
            self.manager.book_seat("screening-1", 2, 3, "bob")

        seats = self.manager.availability("screening-1")
        seat = [s for s in seats if s["row"] == 2 and s["number"] == 3][0]
        self.assertEqual("alice", seat["client_id"])

    def test_availability_lists_every_seat_of_the_room(self):
        seats = self.manager.availability("screening-1")

        self.assertEqual(
            [(row, number) for row in (1, 2, 3) for number in (1, 2, 3, 4)],
            [(seat["row"], seat["number"]) for seat in seats],
        )

    def test_availability_starts_with_every_seat_free(self):
        seats = self.manager.availability("screening-1")

        self.assertTrue(all(seat["available"] for seat in seats))
        self.assertTrue(all(seat["client_id"] is None for seat in seats))

    def test_availability_counts_free_and_booked_seats(self):
        self.manager.book_seat("screening-1", 1, 1, "alice")
        self.manager.book_seat("screening-1", 3, 4, "bob")

        seats = self.manager.availability("screening-1")

        self.assertEqual(10, len([s for s in seats if s["available"]]))
        self.assertEqual(2, len([s for s in seats if not s["available"]]))

    def test_two_screenings_in_the_same_room_book_independently(self):
        self.manager.schedule_screening("screening-2", "room-1")
        self.manager.book_seat("screening-1", 1, 1, "alice")

        booking = self.manager.book_seat("screening-2", 1, 1, "bob")

        self.assertEqual("bob", booking["client_id"])
        self.assertTrue(self.manager.availability("screening-2")[0]["available"] is False)
        self.assertEqual(
            1, len([s for s in self.manager.availability("screening-2") if not s["available"]])
        )

    def test_rejects_a_booking_on_an_unknown_screening(self):
        with self.assertRaises(UnknownScreeningError):
            self.manager.book_seat("screening-404", 1, 1, "alice")

    def test_rejects_availability_of_an_unknown_screening(self):
        with self.assertRaises(UnknownScreeningError):
            self.manager.availability("screening-404")

    def test_rejects_a_screening_in_an_unknown_room(self):
        with self.assertRaises(UnknownRoomError):
            self.manager.schedule_screening("screening-2", "room-404")

    def test_rejects_a_seat_outside_the_room(self):
        # Row and seat numbers start at 1 and stop at the room's dimensions.
        for row, number in [(0, 1), (4, 1), (1, 0), (1, 5)]:
            with self.subTest(row=row, number=number):
                with self.assertRaises(NoSuchSeatError):
                    self.manager.book_seat("screening-1", row, number, "alice")

    def test_rejects_a_room_without_rows(self):
        with self.assertRaises(ValueError):
            self.manager.register_room("room-2", row_count=0, seats_per_row=4)

    def test_rejects_a_room_without_seats(self):
        with self.assertRaises(ValueError):
            self.manager.register_room("room-2", row_count=3, seats_per_row=0)


if __name__ == "__main__":
    unittest.main()
