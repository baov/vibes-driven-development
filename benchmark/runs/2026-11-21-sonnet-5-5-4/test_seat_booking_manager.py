# Standard unittest framework.
import unittest
# Mock used for the logger collaborator.
from unittest import mock

# Classes under test.
from seat_booking import ProcessingException, SeatBookingManager


# One test file for the SeatBookingManager class; one test per public method.
class SeatBookingManagerTest(unittest.TestCase):
    # Build a manager with a mocked logger, a 2-row room and one screening.
    def setUp(self):
        # Mock the only collaborator.
        self.logger = mock.Mock()
        # Manager under test.
        self.manager = SeatBookingManager(self.logger)
        # Room with 2 seats in row 1 and 3 seats in row 2.
        self.manager.add_room("R1", [2, 3])
        # Screening in that room.
        self.manager.add_screening("S1", "R1")

    # Default logger is created when none is injected.
    def test___init__(self):
        # Manager without injected logger.
        data = SeatBookingManager()
        # The default logger is used.
        self.assertIsNotNone(data.logger)

    # add_room stores the room.
    def test_add_room(self):
        # Register another room.
        data = self.manager.add_room("R2", [4])
        # The room id is returned.
        self.assertEqual(data, "R2")

    # add_room rejects a room without rows.
    def test_add_room2(self):
        # Empty rows are rejected and logged.
        with self.assertRaises(ProcessingException):
            self.manager.add_room("R2", [])

    # add_room rejects a row without seats.
    def test_add_room3(self):
        # Zero-seat row is rejected.
        with self.assertRaises(ProcessingException):
            self.manager.add_room("R2", [2, 0])

    # add_room rejects a duplicate room and logs it.
    def test_add_room4(self):
        # Duplicate id is rejected.
        with self.assertRaises(ProcessingException):
            self.manager.add_room("R1", [1])
        # The failure was logged once at this layer.
        self.logger.error.assert_called_once()

    # add_screening stores the screening.
    def test_add_screening(self):
        # Schedule another screening.
        data = self.manager.add_screening("S2", "R1")
        # The screening id is returned.
        self.assertEqual(data, "S2")

    # add_screening rejects an unknown room.
    def test_add_screening2(self):
        # Unknown room is rejected.
        with self.assertRaises(ProcessingException):
            self.manager.add_screening("S2", "nope")

    # add_screening rejects a duplicate screening.
    def test_add_screening3(self):
        # Duplicate id is rejected.
        with self.assertRaises(ProcessingException):
            self.manager.add_screening("S1", "R1")

    # book_seat records the booking.
    def test_book_seat(self):
        # Book row 2 seat 3 (the last seat of the room).
        data = self.manager.book_seat("S1", 2, 3, "client-a")
        # The booked key is returned.
        self.assertEqual(data, ("S1", 2, 3))

    # book_seat rejects an already booked seat.
    def test_book_seat2(self):
        # First booking succeeds.
        self.manager.book_seat("S1", 1, 1, "client-a")
        # Second booking of the same seat is rejected, even for another client.
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("S1", 1, 1, "client-b")

    # book_seat rejects an unknown screening.
    def test_book_seat3(self):
        # Unknown screening is rejected.
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("nope", 1, 1, "client-a")

    # book_seat rejects an unknown row.
    def test_book_seat4(self):
        # Row 3 does not exist.
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("S1", 3, 1, "client-a")

    # book_seat rejects an unknown seat.
    def test_book_seat5(self):
        # Row 1 has only 2 seats.
        with self.assertRaises(ProcessingException):
            self.manager.book_seat("S1", 1, 3, "client-a")

    # get_seat_availability reflects bookings, per screening.
    def test_get_seat_availability(self):
        # Book one seat of S1.
        self.manager.book_seat("S1", 1, 2, "client-a")
        # Read availability of every seat.
        data = self.manager.get_seat_availability("S1")
        # 5 seats, only row 1 seat 2 is taken.
        self.assertEqual(
            [(d["row"], d["seat"], d["available"]) for d in data],
            [(1, 1, True), (1, 2, False), (2, 1, True), (2, 2, True), (2, 3, True)],
        )

    # get_seat_availability rejects an unknown screening.
    def test_get_seat_availability2(self):
        # Unknown screening is rejected.
        with self.assertRaises(ProcessingException):
            self.manager.get_seat_availability("nope")


# Allow running this file directly.
if __name__ == "__main__":
    # Run the tests.
    unittest.main()
