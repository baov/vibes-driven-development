# Import the standard unittest framework for the test cases
import unittest
# Import the mock helpers used to isolate the logger collaborator
from unittest import mock

# Import the class under test and the exceptions it raises
from seat_booking.booking_manager import BookingManager, ProcessingException, SeatAlreadyBookedException


# Define the test case mirroring the BookingManager class, one test per method
class BookingManagerTest(unittest.TestCase):
    # Create a fresh manager for each test, with the logger mocked out
    def setUp(self):
        # Patch the module logger so the collaborator is isolated
        patcher = mock.patch("seat_booking.booking_manager.logger")
        # Start the patch so the logger is replaced for this test
        self.logger = patcher.start()
        # Stop the patch once the test finishes
        self.addCleanup(patcher.stop)
        # Create the manager under test
        self.manager = BookingManager()

    # Check that a new manager starts with no rooms and no screenings
    def test___init__(self):
        # Assert the room map starts empty
        self.assertEqual(self.manager.rooms, {})
        # Assert the screening map starts empty
        self.assertEqual(self.manager.screenings, {})

    # Check that rooms with invalid dimensions are rejected and valid rooms are stored
    def test_add_room(self):
        # Assert that a room without rows is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to register the invalid room
            self.manager.add_room("room-0", 0, 3)
        # Assert that a room without seats is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to register the invalid room
            self.manager.add_room("room-0", 2, 0)
        # Register a valid room
        self.manager.add_room("room-1", 2, 3)
        # Assert the valid room was stored with its dimensions
        self.assertEqual(self.manager.rooms["room-1"], {"rows": 2, "seats_per_row": 3})

    # Check that screenings in unknown rooms are rejected and valid screenings are stored
    def test_add_screening(self):
        # Register a room to schedule screenings in
        self.manager.add_room("room-1", 2, 3)
        # Assert that a screening in an unknown room is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to schedule the screening in the unknown room
            self.manager.add_screening("screening-1", "room-9")
        # Schedule a screening in the existing room
        self.manager.add_screening("screening-1", "room-1")
        # Assert the screening was stored
        self.assertIn("screening-1", self.manager.screenings)

    # Check that seats are booked once, rejected when missing or taken, and scoped per screening
    def test_book_seat(self):
        # Register a room and a screening in it
        self.manager.add_room("room-1", 2, 3)
        self.manager.add_screening("screening-1", "room-1")
        # Assert that booking in an unknown screening is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book in the unknown screening
            self.manager.book_seat("screening-9", 1, 1, "client-a")
        # Assert that a seat beyond the last row is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that does not exist
            self.manager.book_seat("screening-1", 3, 1, "client-a")
        # Assert that a seat below the first number is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to book the seat that does not exist
            self.manager.book_seat("screening-1", 1, 0, "client-a")
        # Book a free seat for the first client
        self.manager.book_seat("screening-1", 1, 1, "client-a")
        # Assert that booking an already booked seat is rejected
        with self.assertRaises(SeatAlreadyBookedException):
            # Attempt to book the same seat for a second client
            self.manager.book_seat("screening-1", 1, 1, "client-b")
        # Schedule a second screening in the same room
        self.manager.add_screening("screening-2", "room-1")
        # Book the same seat in the other screening, which must still be free
        self.manager.book_seat("screening-2", 1, 1, "client-b")
        # Assert the first client holds the seat in the first screening
        self.assertEqual(self.manager.screenings["screening-1"]["booked"][(1, 1)], "client-a")

    # Check that availability lists every seat of the room and flags the booked ones
    def test_seat_availability(self):
        # Register a room and a screening in it
        self.manager.add_room("room-1", 2, 3)
        self.manager.add_screening("screening-1", "room-1")
        # Assert that availability of an unknown screening is rejected
        with self.assertRaises(ProcessingException):
            # Attempt to read the availability of the unknown screening
            self.manager.seat_availability("screening-9")
        # Book one seat so that it shows as unavailable
        self.manager.book_seat("screening-1", 1, 2, "client-a")
        # Read the availability of every seat
        availability = self.manager.seat_availability("screening-1")
        # Assert every seat of the 2x3 room is listed
        self.assertEqual(len(availability), 6)
        # Assert the booked seat is flagged as unavailable
        self.assertEqual(availability[1], {"row": 1, "seat": 2, "available": False})
