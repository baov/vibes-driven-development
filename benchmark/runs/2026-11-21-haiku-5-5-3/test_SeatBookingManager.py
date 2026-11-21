# Import unittest to define the test case run by the standard runner.
import unittest
# Import mock to replace the screening collaborator and the module logger.
from unittest import mock

# Import the class under test and the exception it must raise.
from seat_booking import ProcessingException, SeatBookingManager


# Test case mirroring SeatBookingManager: one test per public method.
class SeatBookingManagerTest(unittest.TestCase):
    # Verifies book_seat records a free seat and rejects booked, out-of-room and failing requests.
    def test_book_seat(self):
        # Build a mocked screening in a 2x3 room with no bookings yet.
        screening = mock.Mock(room=mock.Mock(rows=2, seats_per_row=3), bookings={})
        # Create the manager under test.
        manager = SeatBookingManager()
        # Replace the module logger so the expected rejections do not print to stderr.
        with mock.patch("seat_booking.logger"):
            # Book seat 2 of row 1 for the client.
            manager.book_seat(screening, "client-1", 1, 2)
            # Assert the booking was recorded under the seat key.
            self.assertEqual(screening.bookings, {(1, 2): "client-1"})
            # Assert booking an already booked seat is rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book the same seat again.
                manager.book_seat(screening, "client-2", 1, 2)
            # Assert a seat outside the room is rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book row 3, which does not exist in a two-row room.
                manager.book_seat(screening, "client-2", 3, 1)
            # Assert a missing screening is wrapped in the generic exception.
            with self.assertRaises(ProcessingException):
                # Attempt to book on a screening that is None.
                manager.book_seat(None, "client-2", 1, 1)

    # Verifies get_seat_availability reports every seat as free or booked, and wraps failures.
    def test_get_seat_availability(self):
        # Build a mocked screening in a 2x2 room where seat 1 of row 1 is booked.
        screening = mock.Mock(room=mock.Mock(rows=2, seats_per_row=2), bookings={(1, 1): "client-1"})
        # Create the manager under test.
        manager = SeatBookingManager()
        # Replace the module logger so the expected failure does not print to stderr.
        with mock.patch("seat_booking.logger"):
            # Assert every seat is reported with its availability.
            self.assertEqual(manager.get_seat_availability(screening), {(1, 1): False, (1, 2): True, (2, 1): True, (2, 2): True})
            # Assert a missing screening is wrapped in the generic exception.
            with self.assertRaises(ProcessingException):
                # Request availability for a screening that is None.
                manager.get_seat_availability(None)
