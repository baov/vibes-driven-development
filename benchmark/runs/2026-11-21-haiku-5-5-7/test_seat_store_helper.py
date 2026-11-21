# Import the unittest module that provides the test framework.
import unittest

# Import the store class under test.
from seat_booking import SeatStoreHelper


# Declare the test case that mirrors SeatStoreHelper, with one test per method. The store has no collaborators, so it runs for real.
class SeatStoreHelperTest(unittest.TestCase):
    # Verify that a new store knows no screenings.
    def test___init__(self):
        # Check that looking up any screening in a new store finds no room.
        self.assertIsNone(SeatStoreHelper().find_room("s1"))

    # Verify that saving a screening starts it with no bookings.
    def test_save_screening(self):
        # Create a store that will hold the screening.
        store = SeatStoreHelper()
        # Save a screening with ten rows of twelve seats.
        store.save_screening("s1", 10, 12)
        # Check that the new screening has no bookings.
        self.assertEqual(store.list_bookings("s1"), {})

    # Verify that a saved screening reports its room dimensions.
    def test_find_room(self):
        # Create a store that will hold the screening.
        store = SeatStoreHelper()
        # Save a screening with ten rows of twelve seats.
        store.save_screening("s1", 10, 12)
        # Check that the room of the screening is reported with its dimensions.
        self.assertEqual(store.find_room("s1"), (10, 12))

    # Verify that the bookings of a screening are returned as a copy the caller cannot use to change the store.
    def test_list_bookings(self):
        # Create a store that will hold the screening.
        store = SeatStoreHelper()
        # Save a screening with ten rows of twelve seats.
        store.save_screening("s1", 10, 12)
        # Fetch the bookings and change the returned copy.
        store.list_bookings("s1")[(1, 1)] = "c1"
        # Check that the stored bookings were not changed by the edit to the copy.
        self.assertEqual(store.list_bookings("s1"), {})

    # Verify that a booking is recorded against its seat.
    def test_save_booking(self):
        # Create a store that will hold the screening.
        store = SeatStoreHelper()
        # Save a screening with ten rows of twelve seats.
        store.save_screening("s1", 10, 12)
        # Record that client c1 holds seat one of row one.
        store.save_booking("s1", 1, 1, "c1")
        # Check that the booking is visible in the screening's bookings.
        self.assertEqual(store.list_bookings("s1"), {(1, 1): "c1"})
