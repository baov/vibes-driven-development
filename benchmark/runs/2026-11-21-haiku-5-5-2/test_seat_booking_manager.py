# Standard library test case base and mocking, used to isolate the manager from its logger
import unittest
from unittest import mock

# Class under test and the generic exception it raises at its boundary
from seat_booking import ProcessingException, SeatBookingManager


# Mirror test for SeatBookingManager: one test per method, the module logger mocked as the only collaborator
class SeatBookingManagerTest(unittest.TestCase):
    # Verifies that register_screening logs the registration of the screening
    @mock.patch("seat_booking.logger")
    def test_register_screening(self, logger):
        # Create a fresh manager so no state leaks between tests
        manager = SeatBookingManager()
        # Register a screening held in a room of two rows of three seats
        manager.register_screening("s1", 2, 3)
        # Assert that the registration was logged exactly once
        logger.info.assert_called_once()

    # Verifies that book_seat books free seats and rejects duplicates, out of room and unknown screenings
    @mock.patch("seat_booking.logger")
    def test_book_seat(self, logger):
        # Create a fresh manager so no state leaks between tests
        manager = SeatBookingManager()
        # Register a screening held in a room of two rows of three seats
        manager.register_screening("s1", 2, 3)
        # Book seat (1, 1) for client c1, which must succeed
        manager.book_seat("s1", 1, 1, "c1")
        # Book the same seat again for client c2, which must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the duplicate booking
            manager.book_seat("s1", 1, 1, "c2")
        # Book a seat of a screening that was never registered, which must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking against the unknown screening
            manager.book_seat("missing", 1, 1, "c3")
        # Book a seat that lies outside the room, which must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the booking of the out-of-room seat
            manager.book_seat("s1", 9, 9, "c3")
        # Assert that each of the three rejections was logged as an error
        self.assertEqual(logger.error.call_count, 3)

    # Verifies that get_seat_availability lists every seat with its availability and rejects unknown screenings
    @mock.patch("seat_booking.logger")
    def test_get_seat_availability(self, logger):
        # Create a fresh manager so no state leaks between tests
        manager = SeatBookingManager()
        # Register a screening held in a room of one row of two seats
        manager.register_screening("s1", 1, 2)
        # Book seat (1, 2) so that it is no longer available
        manager.book_seat("s1", 1, 2, "c1")
        # Snapshot the availability of every seat of the screening
        self.assertEqual(
            # Read the availability of screening s1
            manager.get_seat_availability("s1"),
            # Expect seat 1 free and seat 2 taken
            [{"row": 1, "seat": 1, "available": True}, {"row": 1, "seat": 2, "available": False}],
        )
        # Read the availability of a screening that was never registered, which must be rejected
        with self.assertRaises(ProcessingException):
            # Attempt the lookup against the unknown screening
            manager.get_seat_availability("missing")
        # Assert that the rejected lookup was logged as an error
        logger.error.assert_called_once()
