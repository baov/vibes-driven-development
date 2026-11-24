# unittest is the standard test framework used by the project's test command.
import unittest
# unittest.mock provides the doubles for collaborators, as the mirror-testing rules require.
from unittest.mock import MagicMock, patch

# Import the production classes under test from the package root.
from seat_booking import (
    ProcessingException,
    Room,
    Screening,
    SeatAlreadyBookedException,
    SeatBookingManager,
)


# Mirror of Room: one test per method.
class RoomTest(unittest.TestCase):
    # Runs before each test: silence the module logger, a collaborator, so expected failures stay quiet.
    def setUp(self):
        # Create the patch that replaces the module logger.
        patcher = patch("seat_booking.logger")
        # Activate the patch for the duration of the test.
        patcher.start()
        # Deactivate the patch once the test finishes.
        self.addCleanup(patcher.stop)

    # Checks that invalid dimensions are rejected, including non-numeric ones.
    def test_init(self):
        # Zero rows describe no seats and must be rejected.
        with self.assertRaises(ProcessingException):
            # Build a room with no rows.
            Room(0, 5)
        # Non-numeric dimensions must be rejected and wrapped.
        with self.assertRaises(ProcessingException):
            # Build a room with a missing row count.
            Room(None, 5)

    # Checks that seat indices are validated against the layout.
    def test_contains(self):
        # Build a 3x4 room to check boundaries against.
        room = Room(3, 4)
        # The last seat of the last row exists.
        self.assertTrue(room.contains(3, 4))
        # A row beyond the layout does not exist.
        self.assertFalse(room.contains(4, 1))
        # A non-numeric index must be rejected and wrapped.
        with self.assertRaises(ProcessingException):
            # Query with a string row.
            room.contains("a", 1)

    # Checks that every seat of the room is listed.
    def test_seats(self):
        # A 2x3 room has six seats.
        self.assertEqual(len(Room(2, 3).seats()), 6)


# Mirror of Screening: one test per method, with the room mocked.
class ScreeningTest(unittest.TestCase):
    # Runs before each test: silence the logger and build a screening with a mocked room.
    def setUp(self):
        # Create the patch that replaces the module logger.
        patcher = patch("seat_booking.logger")
        # Activate the patch for the duration of the test.
        patcher.start()
        # Deactivate the patch once the test finishes.
        self.addCleanup(patcher.stop)
        # Mock the room collaborator.
        self.room = MagicMock()
        # Build the screening under test around the mocked room.
        self.screening = Screening("s1", self.room)

    # Checks that the constructor accepts the room it is given.
    def test_init(self):
        # Constructing a screening must not touch the room.
        self.room.contains.assert_not_called()

    # Checks booking success, double booking rejection, unknown seats and unexpected failures.
    def test_book(self):
        # Declare that every seat exists in the mocked room.
        self.room.contains.return_value = True
        # Book seat 1-1 for a first client.
        self.screening.book(1, 1, "client-a")
        # Verify the room was asked about the requested seat.
        self.room.contains.assert_called_with(1, 1)
        # A second booking of the same seat must be rejected.
        with self.assertRaises(SeatAlreadyBookedException):
            # Attempt to book the already held seat.
            self.screening.book(1, 1, "client-b")
        # Declare that the requested seat is outside the room.
        self.room.contains.return_value = False
        # Booking a non-existent seat must be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to book a seat outside the layout.
            self.screening.book(9, 9, "client-a")
        # Make the room fail unexpectedly.
        self.room.contains.side_effect = RuntimeError("boom")
        # Unexpected failures must surface as the generic exception.
        with self.assertRaises(ProcessingException):
            # Attempt a booking while the room is failing.
            self.screening.book(1, 2, "client-a")

    # Checks that availability marks held seats as unavailable and free seats as available.
    def test_availability(self):
        # Declare a room of two seats in one row.
        self.room.seats.return_value = [(1, 1), (1, 2)]
        # Declare that every seat exists.
        self.room.contains.return_value = True
        # Hold the first seat.
        self.screening.book(1, 1, "client-a")
        # The report must list each seat with its current availability.
        self.assertEqual(
            self.screening.availability(),
            [
                {"row": 1, "seat": 1, "available": False},
                {"row": 1, "seat": 2, "available": True},
            ],
        )


# Mirror of SeatBookingManager: one test per method, with Screening mocked.
class SeatBookingManagerTest(unittest.TestCase):
    # Runs before each test: silence the logger and replace the Screening class with a mock.
    def setUp(self):
        # Create the patch that replaces the module logger.
        patcher = patch("seat_booking.logger")
        # Activate the logger patch.
        patcher.start()
        # Deactivate the logger patch once the test finishes.
        self.addCleanup(patcher.stop)
        # Create the patch that replaces the Screening class.
        screening_patcher = patch("seat_booking.Screening")
        # Activate the Screening patch and keep the mocked class.
        self.screening_class = screening_patcher.start()
        # Deactivate the Screening patch once the test finishes.
        self.addCleanup(screening_patcher.stop)
        # The instance the mocked class returns, used as the screening collaborator.
        self.screening = self.screening_class.return_value
        # Mock the room collaborator passed to screenings.
        self.room = MagicMock()
        # Build the manager under test.
        self.manager = SeatBookingManager()

    # Checks that a new manager starts with no screenings.
    def test_init(self):
        # Creating a manager must not build any screening.
        self.screening_class.assert_not_called()

    # Checks registration of a screening, duplicate rejection and unexpected failures.
    def test_create_screening(self):
        # Register a new screening.
        self.manager.create_screening("s1", self.room)
        # The screening must be built with its identifier and room.
        self.screening_class.assert_called_once_with("s1", self.room)
        # Registering the same identifier again must be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to register a duplicate.
            self.manager.create_screening("s1", self.room)
        # An unhashable identifier causes an unexpected failure, which must be wrapped.
        with self.assertRaises(ProcessingException):
            # Attempt to register with a list as identifier.
            self.manager.create_screening([], self.room)

    # Checks that bookings are delegated to the right screening and that errors propagate correctly.
    def test_book_seat(self):
        # Register a screening to book against.
        self.manager.create_screening("s1", self.room)
        # A valid request is delegated to the screening.
        self.manager.book_seat("s1", 1, 1, "client-a")
        # The screening must receive the booking arguments.
        self.screening.book.assert_called_once_with(1, 1, "client-a")
        # Booking against an unknown screening must be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to book in a screening that was never registered.
            self.manager.book_seat("unknown", 1, 1, "client-a")
        # Make the screening report a double booking.
        self.screening.book.side_effect = SeatAlreadyBookedException("taken")
        # The double booking must reach the caller with its concrete type.
        with self.assertRaises(SeatAlreadyBookedException):
            # Attempt to book the seat again.
            self.manager.book_seat("s1", 1, 1, "client-b")
        # Make the screening fail unexpectedly.
        self.screening.book.side_effect = RuntimeError("boom")
        # Unexpected failures must surface as the generic exception.
        with self.assertRaises(ProcessingException):
            # Attempt a booking while the screening is failing.
            self.manager.book_seat("s1", 1, 2, "client-a")

    # Checks that availability is read from the right screening and that errors are handled.
    def test_get_seat_availability(self):
        # Register a screening to read from.
        self.manager.create_screening("s1", self.room)
        # Declare the availability the screening reports.
        self.screening.availability.return_value = ["seat-report"]
        # The manager must return the screening's report unchanged.
        self.assertEqual(self.manager.get_seat_availability("s1"), ["seat-report"])
        # Reading an unknown screening must be rejected.
        with self.assertRaises(ProcessingException):
            # Attempt to read a screening that was never registered.
            self.manager.get_seat_availability("unknown")
        # Make the screening fail unexpectedly.
        self.screening.availability.side_effect = RuntimeError("boom")
        # Unexpected failures must surface as the generic exception.
        with self.assertRaises(ProcessingException):
            # Attempt to read while the screening is failing.
            self.manager.get_seat_availability("s1")
