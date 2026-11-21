# Import unittest to structure the test cases and their assertions.
import unittest
# Import mock to replace the module logger, which is the only collaborator, with a test double.
from unittest import mock

# Import the production classes under test.
from seat_booking import ProcessingException, SeatBookingManager


# Define the test case that mirrors SeatBookingManager, one test method per method.
class SeatBookingManagerTest(unittest.TestCase):
    # Verify that the constructor produces a manager.
    def test___init__(self):
        # Create the manager under test.
        manager = SeatBookingManager()
        # Assert that the manager was created.
        self.assertIsNotNone(manager)

    # Verify that add_screening registers a screening, rejects invalid ones, and logs each rejection.
    def test_add_screening(self):
        # Create the manager under test.
        manager = SeatBookingManager()
        # Replace the module logger with a double so that the test neither prints nor depends on logging.
        with mock.patch("seat_booking._LOGGER") as logger:
            # Register a valid screening of two rows with two seats each.
            manager.add_screening("s1", 2, 2)
            # Attempt to register the same id again, which must be rejected.
            with self.assertRaises(ProcessingException):
                # Repeat the registration of the already registered screening.
                manager.add_screening("s1", 2, 2)
            # Attempt to register a room with no rows, which must be rejected.
            with self.assertRaises(ProcessingException):
                # Register a screening with zero rows.
                manager.add_screening("s2", 0, 2)
            # Attempt to register a room whose row count is not a number, which must be wrapped and rejected.
            with self.assertRaises(ProcessingException):
                # Register a screening whose row count cannot be compared with a number.
                manager.add_screening("s3", "x", 2)
            # Assert that the rejections were logged.
            logger.exception.assert_called()

    # Verify that book_seat books free seats and rejects unknown, nonexistent, double-booked and malformed requests.
    def test_book_seat(self):
        # Create the manager under test.
        manager = SeatBookingManager()
        # Replace the module logger with a double so that the test neither prints nor depends on logging.
        with mock.patch("seat_booking._LOGGER") as logger:
            # Register a valid screening of two rows with two seats each.
            manager.add_screening("s1", 2, 2)
            # Book the first seat for a client, which must succeed.
            manager.book_seat("s1", 1, 1, "c1")
            # Attempt to book the same seat again, which must be rejected.
            with self.assertRaises(ProcessingException):
                # Repeat the booking of the seat that is already booked.
                manager.book_seat("s1", 1, 1, "c2")
            # Attempt to book a seat outside the room, which must be rejected.
            with self.assertRaises(ProcessingException):
                # Request a seat whose row and seat numbers do not exist in the room.
                manager.book_seat("s1", 9, 9, "c2")
            # Attempt to book in a screening that was never registered, which must be rejected.
            with self.assertRaises(ProcessingException):
                # Request a seat in an unknown screening.
                manager.book_seat("unknown", 1, 1, "c2")
            # Attempt to book with a row number that is not a number, which must be wrapped and rejected.
            with self.assertRaises(ProcessingException):
                # Request a seat whose row cannot be compared with a number.
                manager.book_seat("s1", "x", 1, "c2")
            # Assert that the rejections were logged.
            logger.exception.assert_called()

    # Verify that get_seat_availability reports every seat of a screening and rejects unknown or malformed ids.
    def test_get_seat_availability(self):
        # Create the manager under test.
        manager = SeatBookingManager()
        # Replace the module logger with a double so that the test neither prints nor depends on logging.
        with mock.patch("seat_booking._LOGGER") as logger:
            # Register a valid screening of two rows with two seats each.
            manager.add_screening("s1", 2, 2)
            # Book the seat in the first row and second column for a client.
            manager.book_seat("s1", 1, 2, "c1")
            # Request the availability of every seat of the screening.
            result = manager.get_seat_availability("s1")
            # Assert that exactly the booked seat is unavailable and every other seat is available.
            self.assertEqual(result, {(1, 1): True, (1, 2): False, (2, 1): True, (2, 2): True})
            # Attempt to read the availability of a screening that was never registered, which must be rejected.
            with self.assertRaises(ProcessingException):
                # Request the availability of an unknown screening.
                manager.get_seat_availability("unknown")
            # Attempt to read the availability with an id that cannot be used as a key, which must be wrapped and rejected.
            with self.assertRaises(ProcessingException):
                # Request the availability using an unhashable value as the screening id.
                manager.get_seat_availability(["s1"])
            # Assert that the rejections were logged.
            logger.exception.assert_called()
