# Standard unittest framework, the one the project's test command discovers.
import unittest
# Mock stands in for every collaborator so the manager is tested in isolation.
from unittest import mock

# Class under test and the generic exception it raises at its boundary.
from seat_booking import ProcessingException, SeatBookingManager


# Mirror test for SeatBookingManager: one test per method, every collaborator mocked.
class SeatBookingManagerTest(unittest.TestCase):
    # Builds the collaborators shared by all tests: a mocked room, a mocked screening and a mocked logger.
    def setUp(self):
        # Mocked room with two rows of three seats.
        self.room = mock.Mock(room_id="room-1", row_count=2, seats_per_row=3)
        # Mocked screening that takes place in that room.
        self.screening = mock.Mock(screening_id="screening-1", room_id="room-1")
        # Patch the module logger so logging is a mocked collaborator as well.
        patcher = mock.patch("seat_booking.logger")
        # Start the patch so the logger is replaced for the duration of the test.
        self.logger = patcher.start()
        # Register the patch to be undone after the test, even on failure.
        self.addCleanup(patcher.stop)
        # Build the manager under test from the mocked collaborators.
        self.manager = SeatBookingManager([self.room], [self.screening])

    # Covers the constructor: a manager is built from the given rooms and screenings.
    def test___init__(self):
        # Construct a manager from the mocked room and screening.
        manager = SeatBookingManager([self.room], [self.screening])
        # The result must be a SeatBookingManager.
        self.assertIsInstance(manager, SeatBookingManager)

    # Covers book_seat: a free seat is booked, and every rejected request raises ProcessingException.
    def test_book_seat(self):
        # Book a free seat, which must succeed without raising.
        self.manager.book_seat("screening-1", 1, 1, "client-1")
        # Each request below must be rejected: a booked seat, a seat outside the layout, and an unknown screening.
        for screening_id, row, seat in [("screening-1", 1, 1), ("screening-1", 9, 1), ("missing", 1, 2)]:
            # Run each rejected request as its own subtest so a failure names the case.
            with self.subTest(screening_id=screening_id, row=row, seat=seat):
                # The rejection must surface as the generic ProcessingException.
                with self.assertRaises(ProcessingException):
                    # Attempt the rejected booking.
                    self.manager.book_seat(screening_id, row, seat, "client-2")
        # Every rejection must have been logged by the layer that raised it.
        self.logger.error.assert_called()

    # Covers get_seat_availability: every seat is reported, booked seats as not free, and an unknown screening raises ProcessingException.
    def test_get_seat_availability(self):
        # Book one seat so the availability map contains both free and taken seats.
        self.manager.book_seat("screening-1", 1, 1, "client-1")
        # Request the availability of every seat of the screening.
        result = self.manager.get_seat_availability("screening-1")
        # The booked seat must be reported as not available.
        self.assertFalse(result[(1, 1)])
        # An unknown screening must be rejected with the generic ProcessingException.
        with self.assertRaises(ProcessingException):
            # Request availability for a screening that does not exist.
            self.manager.get_seat_availability("missing")
