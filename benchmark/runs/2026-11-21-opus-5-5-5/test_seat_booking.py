import threading
import unittest

from seat_booking import (
    ScreeningAlreadyExistsException,
    ScreeningNotFoundException,
    SeatAlreadyBookedException,
    SeatBookingManager,
    SeatNotFoundException,
)


class SeatBookingManagerTest(unittest.TestCase):
    def setUp(self):
        # Fresh manager with a screening in a room of rows A (3 seats) and B (2 seats).
        self.manager = SeatBookingManager()
        # Register the screening used by most tests.
        self.manager.add_screening("s1", {"A": 3, "B": 2})

    def available(self, screening_id):
        # Seats still free for the screening, as (row, seat) pairs.
        return [(s["row"], s["seat"]) for s in self.manager.get_seat_availability(screening_id) if s["available"]]

    # --- add_screening ---

    def test_add_screening_rejects_duplicate_id(self):
        # Book a seat so we can check the existing screening is left untouched.
        self.manager.book_seat("s1", "A", 1, "alice")
        # Re-registering the same id must fail.
        with self.assertRaises(ScreeningAlreadyExistsException):
            self.manager.add_screening("s1", {"A": 3})
        # The original booking survives.
        self.assertNotIn(("A", 1), self.available("s1"))

    def test_add_screening_rejects_empty_room_and_empty_row(self):
        # A room with no rows is invalid.
        with self.assertRaises(ValueError):
            self.manager.add_screening("s2", {})
        # A row with zero seats is invalid.
        with self.assertRaises(ValueError):
            self.manager.add_screening("s2", {"A": 0})

    def test_add_screening_copies_room_layout(self):
        # Layout handed in by the caller.
        rows = {"A": 1}
        # Register a screening with that layout.
        self.manager.add_screening("s2", rows)
        # Mutate the caller's dict afterwards.
        rows["A"] = 5
        # The screening keeps its original single seat.
        self.assertEqual(self.available("s2"), [("A", 1)])

    # --- book_seat ---

    def test_book_seat_marks_seat_unavailable(self):
        # Book seat A2.
        self.manager.book_seat("s1", "A", 2, "alice")
        # Only A2 is gone.
        self.assertEqual(self.available("s1"), [("A", 1), ("A", 3), ("B", 1), ("B", 2)])

    def test_book_seat_rejects_already_booked_seat(self):
        # First booking succeeds.
        self.manager.book_seat("s1", "B", 1, "alice")
        # Second booking of the same seat is rejected, whoever the client.
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", "B", 1, "bob")
        # Same client booking twice is rejected too.
        with self.assertRaises(SeatAlreadyBookedException):
            self.manager.book_seat("s1", "B", 1, "alice")

    def test_book_seat_is_per_screening(self):
        # Second screening in an identical room.
        self.manager.add_screening("s2", {"A": 3, "B": 2})
        # Book A1 for the first screening.
        self.manager.book_seat("s1", "A", 1, "alice")
        # A1 is still bookable for the second screening.
        self.manager.book_seat("s2", "A", 1, "bob")
        # And it is now gone there too.
        self.assertNotIn(("A", 1), self.available("s2"))

    def test_book_seat_rejects_unknown_screening(self):
        # No screening "nope" was registered.
        with self.assertRaises(ScreeningNotFoundException):
            self.manager.book_seat("nope", "A", 1, "alice")

    def test_book_seat_rejects_seat_outside_room(self):
        # Unknown row, seat 0, and a seat number past the end of the row.
        for row, seat in [("Z", 1), ("A", 0), ("A", 4), ("B", 3)]:
            with self.subTest(row=row, seat=seat):
                with self.assertRaises(SeatNotFoundException):
                    self.manager.book_seat("s1", row, seat, "alice")

    def test_book_seat_concurrent_attempts_book_once(self):
        # Outcomes of every booking attempt.
        outcomes = []
        # Start all threads at the same time.
        barrier = threading.Barrier(20)

        def attempt(client_id):
            # Wait for every thread to be ready.
            barrier.wait()
            try:
                # Everyone tries to book the same seat.
                self.manager.book_seat("s1", "A", 1, client_id)
                outcomes.append("ok")
            except SeatAlreadyBookedException:
                outcomes.append("rejected")

        # Launch 20 competing clients.
        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Exactly one booking wins.
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 19)

    # --- get_seat_availability ---

    def test_get_seat_availability_lists_every_seat(self):
        # Book B2.
        self.manager.book_seat("s1", "B", 2, "alice")
        # Every seat of the room is listed, in order, with its availability.
        self.assertEqual(
            self.manager.get_seat_availability("s1"),
            [
                {"row": "A", "seat": 1, "available": True},
                {"row": "A", "seat": 2, "available": True},
                {"row": "A", "seat": 3, "available": True},
                {"row": "B", "seat": 1, "available": True},
                {"row": "B", "seat": 2, "available": False},
            ],
        )

    def test_get_seat_availability_rejects_unknown_screening(self):
        # No screening "nope" was registered.
        with self.assertRaises(ScreeningNotFoundException):
            self.manager.get_seat_availability("nope")


if __name__ == "__main__":
    unittest.main()
