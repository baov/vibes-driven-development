# Import unittest, the standard library test framework.
import unittest
# Import threading to exercise concurrent bookings.
import threading

# Import the public API under test.
from seat_booking import (
    ProcessingException,
    Room,
    SeatAlreadyBookedException,
    SeatBookingManager,
    UnknownSeatException,
)


# Behavioural tests for SeatBookingManager.
class SeatBookingManagerTest(unittest.TestCase):

    # Build a manager with one screening in a 2-row room before each test.
    def setUp(self):
        # Fresh manager per test.
        self.manager = SeatBookingManager()
        # Room with row A of 3 seats and row B of 2 seats.
        self.manager.add_screening("s1", Room("room-1", {"A": 3, "B": 2}))

    # A fresh screening has every seat of its room available.
    def test_all_seats_available_initially(self):
        # Every seat is reported, and all are free.
        self.assertEqual(
            self.manager.get_availability("s1"),
            {("A", 1): True, ("A", 2): True, ("A", 3): True, ("B", 1): True, ("B", 2): True},
        )

    # Booking a seat makes it unavailable and leaves the others free.
    def test_booked_seat_becomes_unavailable(self):
        # Book seat A2.
        self.manager.book_seat("s1", "A", 2, "alice")
        # Fetch availability after booking.
        availability = self.manager.get_availability("s1")
        # A2 is now taken.
        self.assertFalse(availability[("A", 2)])
        # Exactly one seat is taken.
        self.assertEqual(sum(not free for free in availability.values()), 1)

    # Booking an already booked seat is rejected and keeps the first booking.
    def test_double_booking_is_rejected(self):
        # First client books B1.
        self.manager.book_seat("s1", "B", 1, "alice")
        # Second client is rejected on the same seat.
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", "B", 1, "bob")
        # The same client re-booking is also rejected.
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", "B", 1, "alice")
        # The seat is still booked.
        self.assertFalse(self.manager.get_availability("s1")[("B", 1)])

    # Bookings are isolated per screening, even in the same room.
    def test_bookings_are_per_screening(self):
        # Second screening in an identical room.
        self.manager.add_screening("s2", Room("room-1", {"A": 3, "B": 2}))
        # Book A1 for the first screening only.
        self.manager.book_seat("s1", "A", 1, "alice")
        # A1 remains free for the second screening.
        self.assertTrue(self.manager.get_availability("s2")[("A", 1)])
        # And can be booked there.
        self.manager.book_seat("s2", "A", 1, "bob")

    # Seats outside the room are rejected.
    def test_unknown_seat_is_rejected(self):
        # Invalid (row, seat) combinations: unknown row, seat 0, past the row end, non-int.
        for row, seat in [("Z", 1), ("A", 0), ("A", 4), ("B", 3), ("A", "1")]:
            # Each case is checked independently.
            with self.subTest(row=row, seat=seat):
                # The booking is rejected.
                with self.assertRaises(UnknownSeatException):
                    self.manager.book_seat("s1", row, seat, "alice")
        # No booking was recorded.
        self.assertTrue(all(self.manager.get_availability("s1").values()))

    # Unknown screenings are rejected for booking and availability.
    def test_unknown_screening_is_rejected(self):
        # Booking fails.
        with self.assertRaises(UnknownSeatException):
            self.manager.book_seat("nope", "A", 1, "alice")
        # Availability fails.
        with self.assertRaises(UnknownSeatException):
            self.manager.get_availability("nope")

    # Registering the same screening twice is rejected and keeps existing bookings.
    def test_duplicate_screening_is_rejected(self):
        # Book a seat on the existing screening.
        self.manager.book_seat("s1", "A", 1, "alice")
        # Re-registering is refused.
        with self.assertRaises(ProcessingException):
            self.manager.add_screening("s1", Room("room-2", {"A": 1}))
        # The original booking survives.
        self.assertFalse(self.manager.get_availability("s1")[("A", 1)])

    # Under concurrency, exactly one client wins a given seat.
    def test_concurrent_bookings_allow_single_winner(self):
        # Outcomes collected from each thread.
        outcomes = []
        # Barrier so all threads try to book at the same moment.
        barrier = threading.Barrier(20)

        # Each thread attempts to book A1.
        def attempt(client_id):
            # Wait for all threads.
            barrier.wait()
            # Try to book and record the outcome.
            try:
                self.manager.book_seat("s1", "A", 1, client_id)
                outcomes.append("ok")
            except SeatAlreadyBookedException:
                outcomes.append("rejected")

        # Start 20 competing threads.
        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # Exactly one success, all others rejected.
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 19)


# Allow running this file directly.
if __name__ == "__main__":
    unittest.main()
