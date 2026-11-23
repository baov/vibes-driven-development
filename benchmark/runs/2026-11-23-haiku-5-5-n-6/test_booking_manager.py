import unittest

from seat_booking.booking_manager import (
    Booking,
    BookingManager,
    ProcessingException,
    Room,
    Screening,
    Seat,
    SeatAlreadyBookedException,
)


# Tests for BookingManager, one test per method
class BookingManagerTest(unittest.TestCase):

    # Build a manager with one screening in a room of two rows of three seats
    def setUp(self):
        # Manager under test
        self.manager = BookingManager()
        # Room in which the screening takes place
        self.room = Room("Room 1", rows=2, seats_per_row=3)
        # Screening registered in the manager
        self.screening = Screening("s1", self.room)
        # Register the screening
        self.manager.add_screening(self.screening)

    # Registering a screening makes it known, and a missing screening is rejected
    def test_add_screening(self):
        # Register a second screening in the same room
        self.manager.add_screening(Screening("s2", self.room))
        # The second screening now accepts bookings
        self.assertEqual(self.manager.book_seat("s2", 1, 1, "c1"), Booking("s2", 1, 1, "c1"))
        # Registering nothing is a processing failure
        with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
            # Assert the failure is reported to the caller
            with self.assertRaises(ProcessingException):
                # Attempt to register None
                self.manager.add_screening(None)

    # Booking a free seat succeeds, while unknown screenings, invalid seats and taken seats are rejected
    def test_book_seat(self):
        # Booking a free seat returns the booking
        self.assertEqual(self.manager.book_seat("s1", 1, 2, "c1"), Booking("s1", 1, 2, "c1"))
        # Each rejected case is checked on its own
        with self.subTest("taken seat"):
            # A seat booked once cannot be booked again
            with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
                # Assert the double booking is rejected with its own exception
                with self.assertRaises(SeatAlreadyBookedException):
                    # Book the same seat again
                    self.manager.book_seat("s1", 1, 2, "c2")
        with self.subTest("unknown screening"):
            # Booking for an unregistered screening is rejected
            with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
                # Assert the rejection is a processing failure
                with self.assertRaises(ProcessingException):
                    # Book in a screening that does not exist
                    self.manager.book_seat("unknown", 1, 1, "c1")
        with self.subTest("seat outside the room"):
            # Seats beyond the rows and seats of the room are rejected
            with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
                # Assert the rejection is a processing failure
                with self.assertRaises(ProcessingException):
                    # Book a row that does not exist
                    self.manager.book_seat("s1", 3, 1, "c1")
        with self.subTest("unexpected failure"):
            # A screening whose room is missing makes the lookup fail unexpectedly
            self.manager.add_screening(Screening("broken", None))
            # The unexpected failure is logged and wrapped
            with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
                # Assert the caller only sees the generic exception
                with self.assertRaises(ProcessingException):
                    # Book in the broken screening
                    self.manager.book_seat("broken", 1, 1, "c1")

    # Availability lists every seat of the room, row by row, and marks booked seats as unavailable
    def test_get_seat_availability(self):
        # Book one seat so that it shows as unavailable
        self.manager.book_seat("s1", 1, 2, "c1")
        # Ask for the availability of all seats
        seats = self.manager.get_seat_availability("s1")
        # Every seat of the room is reported, in row order, with the booked seat unavailable
        self.assertEqual(
            seats,
            [
                Seat(1, 1, True),
                Seat(1, 2, False),
                Seat(1, 3, True),
                Seat(2, 1, True),
                Seat(2, 2, True),
                Seat(2, 3, True),
            ],
        )
        with self.subTest("unknown screening"):
            # Availability of an unregistered screening is rejected
            with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
                # Assert the rejection is a processing failure
                with self.assertRaises(ProcessingException):
                    # Query a screening that does not exist
                    self.manager.get_seat_availability("unknown")
        with self.subTest("unexpected failure"):
            # A screening whose room is missing makes the lookup fail unexpectedly
            self.manager.add_screening(Screening("broken", None))
            # The unexpected failure is logged and wrapped
            with self.assertLogs("seat_booking.booking_manager", level="ERROR"):
                # Assert the caller only sees the generic exception
                with self.assertRaises(ProcessingException):
                    # Query the broken screening
                    self.manager.get_seat_availability("broken")
