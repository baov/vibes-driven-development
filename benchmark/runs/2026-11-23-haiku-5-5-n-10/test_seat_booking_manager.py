# Import the standard unittest module; the manager has no collaborators, so nothing needs mocking.
import unittest

# Import the class under test and the exception it raises from the package.
from seat_booking import ProcessingException, SeatBookingManager


# Test case for SeatBookingManager, with one test per public method.
class TestSeatBookingManager(unittest.TestCase):
    # Build a fresh manager with one 2x3 room and one screening in it before each test.
    def setUp(self):
        # Create an empty manager for this test.
        self.manager = SeatBookingManager()
        # Register a room with 2 rows and 3 seats per row.
        self.manager.add_room("room-1", 2, 3)
        # Schedule a screening in that room.
        self.manager.add_screening("screening-1", "room-1")

    # Check that a registered room exposes every one of its seats as available.
    def test_add_room(self):
        # Read the availability of the screening so the room layout becomes visible.
        result = self.manager.get_seat_availability("screening-1")
        # Expect six seats, all available, for a 2x3 room.
        self.assertEqual(result, [(r, s, True) for r in (1, 2) for s in (1, 2, 3)])

    # Check that a screening cannot be attached to a room that was never registered.
    def test_add_screening(self):
        # Expect the unknown room to be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to schedule a screening in a missing room.
            self.manager.add_screening("screening-2", "missing-room")

    # Check that a free seat is booked, and that invalid or taken seats are rejected.
    def test_book_seat(self):
        # Book seat 1-1 for a client, which must succeed.
        self.manager.book_seat("screening-1", 1, 1, "client-a")
        # Capture the error logs emitted by the rejected requests below.
        with self.assertLogs(level="ERROR"):
            # Expect booking the same seat again to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to take seat 1-1 a second time.
                self.manager.book_seat("screening-1", 1, 1, "client-b")
            # Expect a row outside the room to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book row 3, which does not exist in a 2-row room.
                self.manager.book_seat("screening-1", 3, 1, "client-b")
            # Expect a seat outside the room to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book seat 4, which does not exist in a 3-seat row.
                self.manager.book_seat("screening-1", 1, 4, "client-b")
            # Expect an unknown screening to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to book a seat for a screening that does not exist.
                self.manager.book_seat("screening-404", 1, 2, "client-b")

    # Check that availability lists every seat in row-then-seat order and marks only the booked one as taken.
    def test_get_seat_availability(self):
        # Book seat 1-2 so that exactly one seat is shown as unavailable.
        self.manager.book_seat("screening-1", 1, 2, "client-a")
        # Read the availability of every seat of the screening.
        result = self.manager.get_seat_availability("screening-1")
        # Expect the full grid with only seat 1-2 marked unavailable.
        self.assertEqual(result, [(r, s, (r, s) != (1, 2)) for r in (1, 2) for s in (1, 2, 3)])
        # Capture the error log emitted by the rejected request below.
        with self.assertLogs(level="ERROR"):
            # Expect availability for an unknown screening to be rejected.
            with self.assertRaises(ProcessingException):
                # Attempt to read availability for a screening that does not exist.
                self.manager.get_seat_availability("screening-404")
