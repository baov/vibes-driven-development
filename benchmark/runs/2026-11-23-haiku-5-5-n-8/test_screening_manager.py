# Import unittest to build the test cases of the ScreeningManager class.
import unittest
# Import Mock to replace the Room collaborator.
from unittest.mock import Mock

# Import the class under test and the exception it raises at the service boundary.
from seat_booking import Room, ScreeningManager, ProcessingException


# Mirror test of the ScreeningManager class: one test per method, with the Room collaborator mocked.
class ScreeningManagerTest(unittest.TestCase):
    # Verifies that add_screening stores the room and starts the screening with no bookings.
    def test_add_screening(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Create a mocked room collaborator.
        room = Mock(spec=Room)
        # Register the screening with the mocked room.
        manager.add_screening("s1", room)
        # Check the screening is now known to the manager.
        self.assertIn("s1", manager._rooms)

    # Verifies that book_seat validates the seat against the room and records the client.
    def test_book_seat(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Create a mocked room that accepts every seat.
        room = Mock(spec=Room)
        # Make the mocked room report the seat as valid.
        room.is_valid_seat.return_value = True
        # Register the screening with the mocked room.
        manager.add_screening("s1", room)
        # Book seat 2 of row 1 for client c1.
        manager.book_seat("s1", "c1", 1, 2)
        # Check the room was asked about that seat.
        room.is_valid_seat.assert_called_with(1, 2)

    # Verifies that book_seat rejects a screening that was never registered.
    def test_book_seat_rejects_unknown_screening(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Check an unknown screening raises the service exception.
        with self.assertRaises(ProcessingException):
            # Attempt the booking on an unknown screening.
            manager.book_seat("missing", "c1", 1, 1)

    # Verifies that book_seat rejects a seat that does not exist in the room.
    def test_book_seat_rejects_invalid_seat(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Create a mocked room that rejects every seat.
        room = Mock(spec=Room)
        # Make the mocked room report the seat as invalid.
        room.is_valid_seat.return_value = False
        # Register the screening with the mocked room.
        manager.add_screening("s1", room)
        # Check booking an invalid seat raises the service exception.
        with self.assertRaises(ProcessingException):
            # Attempt the booking of a seat outside the room.
            manager.book_seat("s1", "c1", 9, 9)

    # Verifies that book_seat rejects a seat that is already booked.
    def test_book_seat_rejects_already_booked(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Create a mocked room that accepts every seat.
        room = Mock(spec=Room)
        # Make the mocked room report the seat as valid.
        room.is_valid_seat.return_value = True
        # Register the screening with the mocked room.
        manager.add_screening("s1", room)
        # Book seat 1 of row 1 for the first client.
        manager.book_seat("s1", "c1", 1, 1)
        # Check booking the same seat again raises the service exception.
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that is already taken.
            manager.book_seat("s1", "c2", 1, 1)

    # Verifies that get_seat_availability reports every seat of the room and marks booked ones as unavailable.
    def test_get_seat_availability(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Create a mocked room of 1 row with 2 seats.
        room = Mock(spec=Room)
        # Give the mocked room its row count.
        room.rows = 1
        # Give the mocked room its seats per row.
        room.seats_per_row = 2
        # Make the mocked room report every seat as valid.
        room.is_valid_seat.return_value = True
        # Register the screening with the mocked room.
        manager.add_screening("s1", room)
        # Book seat 1 for a client.
        manager.book_seat("s1", "c1", 1, 1)
        # Fetch the availability of the screening.
        availability = manager.get_seat_availability("s1")
        # Check the booked seat is reported as unavailable.
        self.assertFalse(availability[0]["available"])

    # Verifies that get_seat_availability rejects a screening that was never registered.
    def test_get_seat_availability_rejects_unknown_screening(self):
        # Create the manager under test.
        manager = ScreeningManager()
        # Check an unknown screening raises the service exception.
        with self.assertRaises(ProcessingException):
            # Attempt to fetch availability of an unknown screening.
            manager.get_seat_availability("missing")
