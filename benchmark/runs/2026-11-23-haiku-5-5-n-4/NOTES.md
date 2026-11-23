# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-4`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in place and committed as `78866a3 update`. The test suite passes (5 tests), and line coverage of the new module is 100% (36 of 36 executable statements, measured with the stdlib `trace` module since coverage.py isn't installed).

**What was added**
- `seat_booking/booking_manager.py` holds everything in one class, `BookingManager`, following the locality rule.
  - `add_room(room_id, rows, seats_per_row)` registers a room and rejects rooms with fewer than one row or one seat.
  - `add_screening(screening_id, room_id)` schedules a screening in an existing room.
  - `book_seat(screening_id, row, seat, client_id)` books a seat. It rejects unknown screenings, seats outside the room, and seats already booked. Double booking raises `SeatAlreadyBookedException`, a subclass of `ProcessingException`.
  - `seat_availability(screening_id)` returns one `{"row", "seat", "available"}` entry for every seat, row by row.
- `tests/test_booking_manager.py` has one test class for `BookingManager` with one test per method. The logger is mocked.

**Choices I made where the request was open**
- Rooms, screenings and bookings are kept in memory. The request didn't mention persistence, so none was added.
- Rows and seats are numbered from 1. A seat is identified by its (row, seat) pair within a screening, so the same seat can be booked in two different screenings.
- Each failure is logged before it is raised, and each new line has a comment above it, as AGENTS.md asks.

**Not done**
- The repo's skills live under `.claude/skills/`, although AGENTS.md refers to `skills/`. I followed the rules in AGENTS.md and didn't touch that mismatch.

**Code-confidence quiz** (from the skill AGENTS.md asks to run after each implementation; it needs your answer, so I'm asking here):
In `seat_booking/booking_manager.py`, which exception is raised when a client books a seat that is already held?
- A. `SeatAlreadyBookedException`
- B. `SeatTakenException`
- C. `DuplicateSeatException`
- D. `ProcessingException`
