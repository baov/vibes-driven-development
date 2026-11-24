# Standard unittest framework, used to define and run the tests.
import unittest
# Mock helpers, used to replace collaborators with test doubles.
from unittest.mock import Mock, patch

# Class under test and the generic exception it must raise on rejected requests.
from seat_booking import ProcessingException, SeatBookingManager


# Test class mirroring SeatBookingManager, with one test per method.
class SeatBookingManagerTest(unittest.TestCase):
    # Verifies that the constructor creates a manager instance.
    def test___init__(self):
        # Build a manager without arguments.
        manager = SeatBookingManager()
        # Check that a manager object was created.
        self.assertIsNotNone(manager)

    # Verifies that add_screening builds a Screening from the id and the room layout.
    @patch("seat_booking.Screening")
    def test_add_screening(self, screening_cls):
        # Create the manager that will register the screening.
        manager = SeatBookingManager()
        # Register a screening with three rows of four seats.
        manager.add_screening("s1", 3, 4)
        # Check that the Screening collaborator was built from the given layout.
        screening_cls.assert_called_once_with("s1", 3, 4)

    # Verifies that book_seat stores a free seat and rejects unknown screenings, missing seats and taken seats.
    @patch("seat_booking.logger")
    @patch("seat_booking.Screening")
    def test_book_seat(self, screening_cls, logger):
        # Replace the Screening collaborator with a double that already holds one booking.
        screening_cls.return_value = Mock(rows=2, seats_per_row=2, bookings={(1, 1): "c0"})
        # Create the manager that will take the bookings.
        manager = SeatBookingManager()
        # Register the screening so the manager knows about it.
        manager.add_screening("s1", 2, 2)
        # Book a free seat for a client.
        manager.book_seat("s1", 1, 2, "c1")
        # Check that the free seat was recorded against the client.
        self.assertEqual(screening_cls.return_value.bookings[(1, 2)], "c1")
        # Attempt to book a seat that is already taken.
        with self.assertRaises(ProcessingException):
            # Request the seat held by the first client.
            manager.book_seat("s1", 1, 1, "c2")
        # Attempt to book a seat outside the room layout.
        with self.assertRaises(ProcessingException):
            # Request a row that does not exist.
            manager.book_seat("s1", 3, 1, "c2")
        # Attempt to book a seat in a screening that was never registered.
        with self.assertRaises(ProcessingException):
            # Request a seat of an unknown screening.
            manager.book_seat("unknown", 1, 1, "c2")
        # Check that every rejected request was logged.
        self.assertEqual(logger.error.call_count, 3)

    # Verifies that get_seat_availability reports every seat and rejects unknown screenings.
    @patch("seat_booking.logger")
    @patch("seat_booking.Screening")
    def test_get_seat_availability(self, screening_cls, logger):
        # Replace the Screening collaborator with a double where the first seat is booked.
        screening_cls.return_value = Mock(rows=1, seats_per_row=2, bookings={(1, 1): "c1"})
        # Create the manager that holds the screenings.
        manager = SeatBookingManager()
        # Register the screening so the manager knows about it.
        manager.add_screening("s1", 1, 2)
        # Request the availability of every seat of the screening.
        availability = manager.get_seat_availability("s1")
        # Check that the booked seat is unavailable and the free seat is available.
        self.assertEqual(availability, {(1, 1): False, (1, 2): True})
        # Attempt to read the availability of a screening that was never registered.
        with self.assertRaises(ProcessingException):
            # Request the availability of an unknown screening.
            manager.get_seat_availability("unknown")
        # Check that the rejected request was logged.
        logger.error.assert_called_once()
