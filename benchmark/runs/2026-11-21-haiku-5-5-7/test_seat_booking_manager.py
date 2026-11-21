# Import the unittest module that provides the test framework.
import unittest
# Import the mock module so the store collaborator can be replaced by a test double.
from unittest import mock

# Import the manager, its exceptions and the store class whose interface the mock follows.
from seat_booking import ProcessingException, SeatAlreadyBookedException, SeatBookingManager, SeatStoreHelper


# Declare the test case that mirrors SeatBookingManager, with one test per method.
class SeatBookingManagerTest(unittest.TestCase):
    # Build a fresh mocked store and a manager wired to it before each test.
    def setUp(self):
        # Create a mock that exposes exactly the methods of the store.
        self.store = mock.Mock(spec=SeatStoreHelper)
        # Create the manager under test with the mocked store injected.
        self.manager = SeatBookingManager(self.store)

    # Verify that a manager built without a store gets a default in-memory store.
    def test___init__(self):
        # Build a manager with no store argument so the default store is created.
        manager = SeatBookingManager()
        # Check that the default store is an in-memory SeatStoreHelper.
        self.assertIsInstance(manager._store, SeatStoreHelper)

    # Verify that a valid screening is saved through the store.
    def test_add_screening(self):
        # Register a screening with ten rows of twelve seats.
        self.manager.add_screening("s1", 10, 12)
        # Check that the store received the screening's room dimensions.
        self.store.save_screening.assert_called_once_with("s1", 10, 12)

    # Verify that a screening with a non-positive row count is rejected.
    def test_add_screening2(self):
        # Check that a zero row count raises a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to register a screening with zero rows.
            self.manager.add_screening("s1", 0, 12)

    # Verify that an unexpected store failure is wrapped in a processing failure.
    def test_add_screening3(self):
        # Make the store fail with an unexpected error.
        self.store.save_screening.side_effect = RuntimeError("storage down")
        # Check that the failure surfaces as a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to register a valid screening while the store is failing.
            self.manager.add_screening("s1", 10, 12)

    # Verify that a seat nobody holds is booked through the store.
    def test_book_seat(self):
        # Report that the screening exists with ten rows of twelve seats.
        self.store.find_room.return_value = (10, 12)
        # Report that no seat of the screening is booked yet.
        self.store.list_bookings.return_value = {}
        # Book seat three of row two for a client.
        self.manager.book_seat("s1", 2, 3, "c1")
        # Check that the store recorded the booking against the seat.
        self.store.save_booking.assert_called_once_with("s1", 2, 3, "c1")

    # Verify that booking a seat that is already booked is rejected.
    def test_book_seat2(self):
        # Report that the screening exists with ten rows of twelve seats.
        self.store.find_room.return_value = (10, 12)
        # Report that seat three of row two is already held by another client.
        self.store.list_bookings.return_value = {(2, 3): "c0"}
        # Check that the second booking of the same seat raises the already-booked rejection.
        with self.assertRaises(SeatAlreadyBookedException):
            # Attempt to book the seat that is already taken.
            self.manager.book_seat("s1", 2, 3, "c1")

    # Verify that booking a seat of an unknown screening is rejected.
    def test_book_seat3(self):
        # Report that the screening does not exist.
        self.store.find_room.return_value = None
        # Check that booking into an unknown screening raises a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat in a screening that was never registered.
            self.manager.book_seat("missing", 1, 1, "c1")

    # Verify that booking a seat outside the room's rows is rejected.
    def test_book_seat4(self):
        # Report that the screening has ten rows of twelve seats.
        self.store.find_room.return_value = (10, 12)
        # Check that a row beyond the room raises a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to book row eleven in a room that has only ten rows.
            self.manager.book_seat("s1", 11, 1, "c1")

    # Verify that an unexpected store failure during booking is wrapped in a processing failure.
    def test_book_seat5(self):
        # Make the store fail with an unexpected error when the room is read.
        self.store.find_room.side_effect = RuntimeError("storage down")
        # Check that the failure surfaces as a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat while the store is failing.
            self.manager.book_seat("s1", 1, 1, "c1")

    # Verify that the availability of every seat is reported, marking booked seats as unavailable.
    def test_get_seat_availability(self):
        # Report that the screening has one row of two seats.
        self.store.find_room.return_value = (1, 2)
        # Report that the first seat is held by a client.
        self.store.list_bookings.return_value = {(1, 1): "c1"}
        # Check that the availability map covers both seats with the right flags.
        self.assertEqual(self.manager.get_seat_availability("s1"), {(1, 1): False, (1, 2): True})

    # Verify that asking for the availability of an unknown screening is rejected.
    def test_get_seat_availability2(self):
        # Report that the screening does not exist.
        self.store.find_room.return_value = None
        # Check that the query raises a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to read the availability of a screening that was never registered.
            self.manager.get_seat_availability("missing")

    # Verify that an unexpected store failure during an availability read is wrapped in a processing failure.
    def test_get_seat_availability3(self):
        # Make the store fail with an unexpected error when the room is read.
        self.store.find_room.side_effect = RuntimeError("storage down")
        # Check that the failure surfaces as a processing failure.
        with self.assertRaises(ProcessingException):
            # Attempt to read availability while the store is failing.
            self.manager.get_seat_availability("s1")
