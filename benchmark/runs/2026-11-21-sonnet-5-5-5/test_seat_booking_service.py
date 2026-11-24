# Tests mirroring seat_booking/seat_booking_service.py: one test per public method,
# plus numbered extras for the remaining branches (100% line coverage).
import unittest

from seat_booking.seat_booking_service import (
    ProcessingException, Room, Screening, SeatAlreadyBookedException, SeatBookingService)


class SeatBookingServiceTest(unittest.TestCase):
    # Fresh service with one 2x3 screening before each test.
    def setUp(self):
        self.service = SeatBookingService()
        self.service.register_screening(Screening("s1", Room(2, 3)))

    def test_register_screening(self):
        self.service.register_screening(Screening("s2", Room(1, 1)))
        self.assertIn("s2", self.service.screenings)

    def test_book_seat(self):
        # Booking succeeds once, and a second booking of the same seat is rejected.
        self.service.book_seat("s1", "alice", 1, 2)
        with self.assertRaises(SeatAlreadyBookedException):
            self.service.book_seat("s1", "bob", 1, 2)

    def test_book_seat2(self):
        # Unknown screening is rejected.
        with self.assertRaises(ProcessingException):
            self.service.book_seat("nope", "alice", 1, 1)

    def test_book_seat3(self):
        # Seats outside the room are rejected.
        with self.assertRaises(ProcessingException):
            self.service.book_seat("s1", "alice", 3, 1)

    def test_get_seat_availability(self):
        # Every seat is listed; only the booked one is unavailable.
        self.service.book_seat("s1", "alice", 2, 3)
        result = self.service.get_seat_availability("s1")
        self.assertEqual(6, len(result))
        self.assertEqual([(2, 3)], [seat for seat, free in result.items() if not free])

    def test_get_seat_availability2(self):
        with self.assertRaises(ProcessingException):
            self.service.get_seat_availability("nope")

    def test__get_screening(self):
        self.assertEqual("s1", self.service._get_screening("s1").id)

    def test__check_seat_exists(self):
        self.service._check_seat_exists(self.service.screenings["s1"], 2, 3)


if __name__ == "__main__":
    unittest.main()
