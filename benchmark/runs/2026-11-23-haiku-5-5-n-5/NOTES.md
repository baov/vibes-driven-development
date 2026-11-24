# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-5`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in and committed as `0d77596 update`. All 8 tests pass with `python3 -m unittest discover -s tests -t .`, and the new code is at 100% statement coverage (measured with a stdlib `trace` script, since no coverage tool is installed).

**What's there**
- `seat_booking/__init__.py`: `SeatBookingManager` with three methods:
  - `add_screening(screening_id, rows, seats_per_row)` registers a screening's room. Re-registering an existing id is rejected, so bookings can't be wiped.
  - `book_seat(screening_id, client_id, row, seat)` books a seat. A seat already held by another booking raises `SeatAlreadyBookedException`. Unknown screenings and out-of-range seats are rejected too.
  - `get_seat_availability(screening_id)` returns one `{"row", "seat", "available"}` entry for every seat in the room, ordered by row then seat.
- `ProcessingException` is the generic wrapper, and `SeatAlreadyBookedException` subclasses it.
- `tests/test_seat_booking_manager.py`: one test file for the one class.

**Choices I made**
- Storage is in memory. The task didn't mention persistence, so I left it out.
- Rows and seats are numbered from 1.
- I followed AGENTS.md: everything is in the existing module, the class has a role suffix, each new line has a comment above it, and errors are logged and wrapped at the boundary.
- The commit message is `update`, the preferred short form. The history had only `init`, so there was no clash to avoid.

**Deviation from the test skill:** it asks for exactly one test per method. I added extra tests for the rejection paths (duplicate screening, already booked, nonexistent seat, unknown screening), because without them the error branches aren't exercised. The coverage contract needs them.

**Code-confidence quiz** (per the AGENTS.md rule to run it after implementation; I'm not waiting on the answer):

In `seat_booking/__init__.py`, which exception does `book_seat` raise when the seat is already held?
- A. ProcessingException
- B. SeatAlreadyBookedException
- C. SeatBookingError
- D. ValueError

Answer: B.
