# Import unittest to structure the test cases
import unittest
# Import MagicMock to stand in for collaborators and patch to replace them
from unittest.mock import MagicMock, patch

# Import the class under test and the generic exception it raises
from seat_booking import ProcessingException, ScreeningManager


# Test case mirroring the ScreeningManager class
class ScreeningManagerTest(unittest.TestCase):
    # Verify that scheduling a screening builds it from the identifier and the room
    @patch("seat_booking.logger")
    @patch("seat_booking.Screening")
    def test_schedule_screening(self, screening_cls, logger):
        # Create a mocked room for the screening
        room = MagicMock()
        # Create the manager under test
        manager = ScreeningManager()
        # Schedule a screening of the mocked room
        manager.schedule_screening("s1", room)
        # Assert that the screening was built from the identifier and the room
        screening_cls.assert_called_once_with("s1", room)

    # Verify that scheduling a duplicate identifier is rejected and logged
    @patch("seat_booking.logger")
    def test_schedule_screening_rejects_duplicate(self, logger):
        # Create the manager under test
        manager = ScreeningManager()
        # Pre-register a screening under the identifier that will be reused
        manager._screenings = {"s1": MagicMock()}
        # Expect the second scheduling of the same identifier to fail
        with self.assertRaises(ProcessingException):
            # Schedule a screening with the duplicate identifier
            manager.schedule_screening("s1", MagicMock())
        # Assert the duplicate was logged
        logger.error.assert_called_once()

    # Verify that a free seat of a known screening is recorded for the client
    def test_book_seat(self):
        # Create a mocked screening whose room has one seat
        screening = MagicMock()
        # Configure the mocked room to list the single seat
        screening.room.seats.return_value = [(1, 1)]
        # Replace the bookings with a mock to observe the recorded seat
        screening.bookings = MagicMock()
        # Create the manager under test
        manager = ScreeningManager()
        # Register the mocked screening under its identifier
        manager._screenings = {"s1": screening}
        # Book the seat for a client
        manager.book_seat("s1", (1, 1), "client-a")
        # Assert that the client was recorded as the holder of the seat
        screening.bookings.__setitem__.assert_called_once_with((1, 1), "client-a")

    # Verify that booking a seat of an unknown screening is rejected and logged
    @patch("seat_booking.logger")
    def test_book_seat_rejects_unknown_screening(self, logger):
        # Create the manager under test with no screening registered
        manager = ScreeningManager()
        # Expect the booking against an unknown screening to fail
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat of a screening that does not exist
            manager.book_seat("missing", (1, 1), "client-a")
        # Assert the unknown screening was logged
        logger.error.assert_called_once()

    # Verify that booking a seat absent from the room is rejected and logged
    @patch("seat_booking.logger")
    def test_book_seat_rejects_seat_outside_room(self, logger):
        # Create a mocked screening whose room has no seats
        screening = MagicMock()
        # Configure the mocked room to list no seats
        screening.room.seats.return_value = []
        # Create the manager under test
        manager = ScreeningManager()
        # Register the mocked screening under its identifier
        manager._screenings = {"s1": screening}
        # Expect the booking of a seat outside the room to fail
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat that the room does not have
            manager.book_seat("s1", (9, 9), "client-a")
        # Assert the missing seat was logged
        logger.error.assert_called_once()

    # Verify that booking a seat that is already booked is rejected and logged
    @patch("seat_booking.logger")
    def test_book_seat_rejects_booked_seat(self, logger):
        # Create a mocked screening whose room has one seat
        screening = MagicMock()
        # Configure the mocked room to list the single seat
        screening.room.seats.return_value = [(1, 1)]
        # Configure the mocked bookings to report the seat as already taken
        screening.bookings.__contains__.return_value = True
        # Create the manager under test
        manager = ScreeningManager()
        # Register the mocked screening under its identifier
        manager._screenings = {"s1": screening}
        # Expect the second booking of the same seat to fail
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that is already taken
            manager.book_seat("s1", (1, 1), "client-b")
        # Assert the double booking was logged
        logger.error.assert_called_once()

    # Verify that the availability of every seat is reported as free or taken
    def test_get_seat_availability(self):
        # Create a mocked screening whose room has two seats
        screening = MagicMock()
        # Configure the mocked room to list both seats
        screening.room.seats.return_value = [(1, 1), (1, 2)]
        # Configure the mocked bookings so that only the first seat is taken
        screening.bookings.__contains__.side_effect = lambda seat: seat == (1, 1)
        # Create the manager under test
        manager = ScreeningManager()
        # Register the mocked screening under its identifier
        manager._screenings = {"s1": screening}
        # Assert that the first seat is taken and the second one is free
        self.assertEqual(manager.get_seat_availability("s1"), {(1, 1): False, (1, 2): True})

    # Verify that querying the availability of an unknown screening is rejected and logged
    @patch("seat_booking.logger")
    def test_get_seat_availability_rejects_unknown_screening(self, logger):
        # Create the manager under test with no screening registered
        manager = ScreeningManager()
        # Expect the query against an unknown screening to fail
        with self.assertRaises(ProcessingException):
            # Attempt to report on a screening that does not exist
            manager.get_seat_availability("missing")
        # Assert the unknown screening was logged
        logger.error.assert_called_once()
