# Standard unittest framework used to run the test cases
import unittest
# Mock helpers used to replace collaborators with controlled doubles
from unittest.mock import MagicMock, patch

# Class under test and the generic failure it raises
from seat_booking import ProcessingException, SeatBookingManager


# Test case mirroring the production class SeatBookingManager
class SeatBookingManagerTest(unittest.TestCase):
    # Build a fresh manager with the module logger mocked before every test
    def setUp(self):
        # Create the class under test
        self.manager = SeatBookingManager()
        # Patch the module logger so logging is a mocked collaborator
        logger_patcher = patch("seat_booking.logger")
        # Activate the logger patch for this test
        logger_patcher.start()
        # Deactivate the logger patch once the test ends
        self.addCleanup(logger_patcher.stop)

    # Verify that a new manager starts with an empty registry
    def test_init(self):
        # Check that the registry of screenings is empty
        self.assertEqual(SeatBookingManager().screenings, {})

    # Verify that add_screening creates an entity with the given layout
    @patch("seat_booking.ScreeningEntity")
    def test_add_screening(self, screening_entity_class):
        # Register a screening in a room of two rows and three seats per row
        self.manager.add_screening("s1", 2, 3)
        # Check that the entity was created with the identifier and the layout
        screening_entity_class.assert_called_once_with("s1", 2, 3)

    # Verify that registering an identifier already in use is rejected
    def test_add_screening2(self):
        # Pre-register a mocked screening under the identifier to be reused
        self.manager.screenings = {"s1": MagicMock()}
        # Check that the duplicate registration raises the generic failure
        with self.assertRaises(ProcessingException):
            # Attempt to register the same identifier a second time
            self.manager.add_screening("s1", 2, 3)

    # Verify that a free seat of an existing screening is recorded as booked
    def test_book_seat(self):
        # Create a mocked screening entity for a room of two rows and three seats
        screening = MagicMock(rows=2, seats_per_row=3)
        # Mock the set of booked seats
        screening.booked_seats = MagicMock()
        # Make the membership check report that the seat is free
        screening.booked_seats.__contains__.return_value = False
        # Register the mocked screening with the manager
        self.manager.screenings = {"s1": screening}
        # Book the seat in the second row, third seat
        self.manager.book_seat("s1", 1, 2)
        # Check that the seat was added to the booked seats
        screening.booked_seats.add.assert_called_once_with((1, 2))

    # Verify that booking a seat that is already booked is rejected
    def test_book_seat2(self):
        # Create a mocked screening entity for a room of two rows and three seats
        screening = MagicMock(rows=2, seats_per_row=3)
        # Mock the set of booked seats
        screening.booked_seats = MagicMock()
        # Make the membership check report that the seat is already booked
        screening.booked_seats.__contains__.return_value = True
        # Register the mocked screening with the manager
        self.manager.screenings = {"s1": screening}
        # Check that booking the taken seat raises the generic failure
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat in the second row, third seat
            self.manager.book_seat("s1", 1, 2)

    # Verify that booking a seat of an unknown screening is rejected
    def test_book_seat3(self):
        # Register no screenings so that the identifier is unknown
        self.manager.screenings = {}
        # Check that booking on an unknown screening raises the generic failure
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat on the unknown screening
            self.manager.book_seat("s1", 0, 0)

    # Verify that booking a seat outside the room layout is rejected
    def test_book_seat4(self):
        # Create a mocked screening entity for a room of two rows and three seats
        screening = MagicMock(rows=2, seats_per_row=3)
        # Mock the set of booked seats
        screening.booked_seats = MagicMock()
        # Register the mocked screening with the manager
        self.manager.screenings = {"s1": screening}
        # Check that a seat in a non-existent row raises the generic failure
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat in row two, which does not exist
            self.manager.book_seat("s1", 2, 0)

    # Verify that the availability of every seat is reported for a screening
    def test_get_seat_availability(self):
        # Create a mocked screening entity for a room of two rows and two seats
        screening = MagicMock(rows=2, seats_per_row=2)
        # Mock the set of booked seats
        screening.booked_seats = MagicMock()
        # Report only the first row, second seat as booked
        screening.booked_seats.__contains__.side_effect = lambda seat: seat == (0, 1)
        # Register the mocked screening with the manager
        self.manager.screenings = {"s1": screening}
        # Read the availability of every seat of the screening
        availability = self.manager.get_seat_availability("s1")
        # Check that each seat is mapped to whether it is still free
        self.assertEqual(availability, {(0, 0): True, (0, 1): False, (1, 0): True, (1, 1): True})

    # Verify that reading the availability of an unknown screening is rejected
    def test_get_seat_availability2(self):
        # Register no screenings so that the identifier is unknown
        self.manager.screenings = {}
        # Check that reading availability of an unknown screening raises the generic failure
        with self.assertRaises(ProcessingException):
            # Attempt to read the availability of the unknown screening
            self.manager.get_seat_availability("s1")
