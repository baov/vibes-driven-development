# Standard unittest framework
import unittest
# Mock used to isolate the service from its logger collaborator
from unittest import mock

# Code under test
from seat_booking import (
    InvalidSeatException,
    Room,
    Screening,
    SeatAlreadyBookedException,
    SeatBookingManagerService,
    UnknownScreeningException,
)


# Mirror test of SeatBookingManagerService: one test per public method, extra numbered tests for remaining lines
class SeatBookingManagerServiceTest(unittest.TestCase):
    # Fresh service with one 2x3 screening, logger mocked
    def setUp(self):
        # Silence and isolate the logger collaborator
        patcher = mock.patch("seat_booking.LOGGER")
        # Start the patch
        patcher.start()
        # Stop it after each test
        self.addCleanup(patcher.stop)
        # Service under test
        self.service = SeatBookingManagerService()
        # Screening in a room of 2 rows and 3 seats per row
        self.service.add_screening(Screening("s1", "Movie", Room("R1", 2, 3)))

    # add_screening: a registered screening can be queried
    def test_add_screening(self):
        # Six seats exist for the registered screening
        self.assertEqual(6, len(self.service.get_seat_availability("s1")))

    # add_screening: re-registering keeps existing bookings
    def test_add_screening2(self):
        # Book a seat
        self.service.book_seat("s1", 1, 1, "c1")
        # Register the same screening again
        self.service.add_screening(Screening("s1", "Movie", Room("R1", 2, 3)))
        # The seat is still booked
        self.assertFalse(self.service.get_seat_availability("s1")[0]["available"])

    # add_screening: failure is logged and rethrown
    def test_add_screening3(self):
        # A screening without attributes makes registration fail and the error propagates
        with self.assertRaises(AttributeError):
            # Invalid argument
            self.service.add_screening(None)

    # book_seat: nominal booking
    def test_book_seat(self):
        # The booking describes the seat and the client
        self.assertEqual(
            {"screening_id": "s1", "row": 2, "seat": 3, "client_id": "c1"},
            self.service.book_seat("s1", 2, 3, "c1"),
        )

    # book_seat: booking an already booked seat is rejected
    def test_book_seat2(self):
        # First booking succeeds
        self.service.book_seat("s1", 1, 2, "c1")
        # Second booking of the same seat, even by another client, is rejected
        with self.assertRaises(SeatAlreadyBookedException):
            # Same seat
            self.service.book_seat("s1", 1, 2, "c2")

    # book_seat: unknown screening is rejected
    def test_book_seat3(self):
        # Unknown id
        with self.assertRaises(UnknownScreeningException):
            # Book on a screening that does not exist
            self.service.book_seat("nope", 1, 1, "c1")

    # book_seat: seat outside the room is rejected
    def test_book_seat4(self):
        # Row 3 does not exist in a 2-row room
        with self.assertRaises(InvalidSeatException):
            # Out-of-range seat
            self.service.book_seat("s1", 3, 1, "c1")

    # book_seat: seat 0 is rejected (numbering starts at 1)
    def test_book_seat5(self):
        # Seat 0 does not exist
        with self.assertRaises(InvalidSeatException):
            # Out-of-range seat
            self.service.book_seat("s1", 1, 0, "c1")

    # get_seat_availability: every seat is listed, booked ones are unavailable
    def test_get_seat_availability(self):
        # Book one seat
        self.service.book_seat("s1", 2, 1, "c1")
        # Availability of the 6 seats in row-then-seat order
        self.assertEqual(
            [False if (r, s) == (2, 1) else True for r in (1, 2) for s in (1, 2, 3)],
            [e["available"] for e in self.service.get_seat_availability("s1")],
        )

    # get_seat_availability: unknown screening is rejected
    def test_get_seat_availability2(self):
        # Unknown id
        with self.assertRaises(UnknownScreeningException):
            # Query a screening that does not exist
            self.service.get_seat_availability("nope")


# Allow running the file directly
if __name__ == "__main__":
    # Run the tests
    unittest.main()
