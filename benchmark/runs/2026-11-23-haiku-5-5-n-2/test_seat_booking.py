# Standard unittest framework used by the repository test runner
import unittest
# Patch helper used to replace the collaborator of the manager with a mock
from unittest.mock import patch

# Production classes under test, imported from the package
from seat_booking import Booking, ProcessingException, Room, SeatAvailability, SeatBookingManager


# Tests of the Room class, which has no collaborators
class RoomTest(unittest.TestCase):
    # Checks that the constructor stores the layout of the room
    def test___init__(self):
        # Build a room with two rows
        room = Room("r1", 2, 3)
        # Check that the number of rows was stored
        self.assertEqual(room.rows, 2)

    # Checks that a room without rows or seats is rejected
    def test___init__2(self):
        # Expect the invalid layout to raise an error
        with self.assertRaises(ValueError):
            # Build a room with no rows
            Room("r1", 0, 3)

    # Checks that a seat inside the layout is found
    def test_has_seat(self):
        # Build a room with two rows of three seats
        room = Room("r1", 2, 3)
        # Check that the last seat of the last row exists
        self.assertTrue(room.has_seat(2, 3))

    # Checks that a seat outside the layout is not found
    def test_has_seat2(self):
        # Build a room with two rows of three seats
        room = Room("r1", 2, 3)
        # Check that a row beyond the layout does not exist
        self.assertFalse(room.has_seat(3, 1))

    # Checks that every seat is listed in reading order
    def test_seat_positions(self):
        # Build a room with one row of two seats
        room = Room("r1", 1, 2)
        # Check the positions listed for the room
        self.assertEqual(room.seat_positions(), [(1, 1), (1, 2)])


# Tests of the SeatBookingManager class, with its Room collaborator mocked
class SeatBookingManagerTest(unittest.TestCase):
    # Prepares a manager holding one room and one screening, with the room class mocked
    def setUp(self):
        # Patcher replacing the Room class used by the manager
        patcher = patch("seat_booking.Room")
        # Start the patch so the manager receives the mocked class
        self.room_class = patcher.start()
        # Stop the patch once the test has finished
        self.addCleanup(patcher.stop)
        # Mocked room instance returned by the mocked class
        self.room = self.room_class.return_value
        # Manager under test
        self.manager = SeatBookingManager()
        # Register the room with a layout of two rows of two seats
        self.manager.add_room("r1", 2, 2)
        # Schedule the screening in that room
        self.manager.add_screening("s1", "r1")

    # Checks that a new manager is created
    def test___init__(self):
        # Check that the constructor returns a manager
        self.assertIsInstance(SeatBookingManager(), SeatBookingManager)

    # Checks that a room is built from its layout
    def test_add_room(self):
        # Register a second room with a different layout
        self.manager.add_room("r2", 4, 5)
        # Check that the room class received the layout
        self.room_class.assert_called_with("r2", 4, 5)

    # Checks that an invalid room layout is rejected with the generic exception
    def test_add_room2(self):
        # Make the room class reject the layout
        self.room_class.side_effect = ValueError("invalid layout")
        # Expect the generic exception from the manager
        with self.assertRaises(ProcessingException):
            # Register a room with an invalid layout
            self.manager.add_room("r3", 0, 0)

    # Checks that a screening is scheduled in a registered room
    def test_add_screening(self):
        # Schedule a second screening in the existing room
        self.assertIsNone(self.manager.add_screening("s2", "r1"))

    # Checks that a screening in an unknown room is rejected
    def test_add_screening2(self):
        # Expect the unknown room to be rejected
        with self.assertRaises(ProcessingException):
            # Schedule a screening in a room that was never registered
            self.manager.add_screening("s2", "missing")

    # Checks that a duplicate screening identifier is rejected
    def test_add_screening3(self):
        # Expect the duplicate screening to be rejected
        with self.assertRaises(ProcessingException):
            # Schedule a screening under an identifier already in use
            self.manager.add_screening("s1", "r1")

    # Checks that an unexpected failure while scheduling is wrapped in the generic exception
    def test_add_screening4(self):
        # Expect an unhashable room identifier to be wrapped
        with self.assertRaises(ProcessingException):
            # Pass a list, which cannot be looked up as a room identifier
            self.manager.add_screening("s2", [])

    # Checks that a free seat is booked for the client
    def test_book_seat(self):
        # Make the room report that the seat exists
        self.room.has_seat.return_value = True
        # Book the seat in the first row, second seat
        booking = self.manager.book_seat("s1", 1, 2, "c1")
        # Check the confirmation returned for the booking
        self.assertEqual(booking, Booking("s1", 1, 2, "c1"))

    # Checks that a seat that is already booked is rejected
    def test_book_seat2(self):
        # Make the room report that the seat exists
        self.room.has_seat.return_value = True
        # Book the seat once for the first client
        self.manager.book_seat("s1", 1, 2, "c1")
        # Expect the second booking of the same seat to be rejected
        with self.assertRaises(ProcessingException):
            # Try to book the same seat for another client
            self.manager.book_seat("s1", 1, 2, "c2")

    # Checks that a booking for an unknown screening is rejected
    def test_book_seat3(self):
        # Expect the unknown screening to be rejected
        with self.assertRaises(ProcessingException):
            # Book a seat for a screening that was never scheduled
            self.manager.book_seat("missing", 1, 1, "c1")

    # Checks that a seat outside the room layout is rejected
    def test_book_seat4(self):
        # Make the room report that the seat does not exist
        self.room.has_seat.return_value = False
        # Expect the missing seat to be rejected
        with self.assertRaises(ProcessingException):
            # Book a seat that the room does not contain
            self.manager.book_seat("s1", 9, 9, "c1")

    # Checks that an unexpected failure while booking is wrapped in the generic exception
    def test_book_seat5(self):
        # Make the room fail when asked about a non-numeric seat
        self.room.has_seat.side_effect = TypeError("not a number")
        # Expect the failure to be wrapped in the generic exception
        with self.assertRaises(ProcessingException):
            # Book a seat whose row is not a number
            self.manager.book_seat("s1", "a", 1, "c1")

    # Checks that every seat is reported with its availability
    def test_get_seat_availability(self):
        # Make the room report two seats in reading order
        self.room.seat_positions.return_value = [(1, 1), (1, 2)]
        # Make the room report that every seat exists
        self.room.has_seat.return_value = True
        # Book the first seat for a client
        self.manager.book_seat("s1", 1, 1, "c1")
        # Check the availability of both seats
        self.assertEqual(
            self.manager.get_seat_availability("s1"),
            [SeatAvailability(1, 1, False), SeatAvailability(1, 2, True)],
        )

    # Checks that availability for an unknown screening is rejected
    def test_get_seat_availability2(self):
        # Expect the unknown screening to be rejected
        with self.assertRaises(ProcessingException):
            # Ask for the availability of a screening that was never scheduled
            self.manager.get_seat_availability("missing")

    # Checks that an unexpected failure while reading the room is wrapped in the generic exception
    def test_get_seat_availability3(self):
        # Make the room fail when its seats are listed
        self.room.seat_positions.side_effect = RuntimeError("room unavailable")
        # Expect the failure to be wrapped in the generic exception
        with self.assertRaises(ProcessingException):
            # Ask for the availability of the screening
            self.manager.get_seat_availability("s1")
