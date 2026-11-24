import unittest

from seat_booking import (BookingService, Room, Screening, SeatAlreadyBookedError,
                          UnknownScreeningError, UnknownSeatError)


class BookingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = BookingService()
        self.service.add_screening(Screening("s1", "Film", Room("A", 2, 3)))
        self.service.add_screening(Screening("s2", "Film", Room("A", 2, 3)))

    def test_all_seats_available_initially(self):
        availability = self.service.availability("s1")
        self.assertEqual(6, len(availability))
        self.assertTrue(all(availability.values()))

    def test_book_marks_seat_unavailable(self):
        self.service.book("s1", 1, 2, "alice")
        availability = self.service.availability("s1")
        self.assertFalse(availability[(1, 2)])
        self.assertTrue(availability[(1, 1)])

    def test_double_booking_rejected(self):
        self.service.book("s1", 1, 2, "alice")
        with self.assertRaises(SeatAlreadyBookedError):
            self.service.book("s1", 1, 2, "bob")

    def test_bookings_are_per_screening(self):
        self.service.book("s1", 1, 2, "alice")
        self.service.book("s2", 1, 2, "bob")
        self.assertTrue(self.service.availability("s2")[(1, 1)])

    def test_unknown_seat_and_screening(self):
        with self.assertRaises(UnknownSeatError):
            self.service.book("s1", 3, 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.book("nope", 1, 1, "alice")
        with self.assertRaises(UnknownScreeningError):
            self.service.availability("nope")
