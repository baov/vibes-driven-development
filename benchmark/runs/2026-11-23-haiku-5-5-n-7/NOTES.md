# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-7`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in place and committed as `88f295a` (message `update`). The suite passes (3 tests), and line coverage of the service is 100%.

**What was added**

- `seat_booking/__init__.py` holds the service. `SeatBookingManager` has three methods:
  - `add_screening(screening_id, rows, seats_per_row)` registers a screening in a room with that layout.
  - `book_seat(screening_id, row, seat, client_id)` books a seat. A seat that is already booked raises `SeatAlreadyBookedException`. Out-of-range seats and unknown screenings raise `ProcessingException`.
  - `get_seat_availability(screening_id)` returns one entry per seat in row-major order, like `{"row": 1, "seat": 2, "available": False}`.
- `tests/test_seat_booking_manager.py` has one test per public method, with the logger mocked.

**Choices I made**

- **Storage is in memory.** The task didn't name a store, so there is no persistence. A lock makes the check-then-book step atomic across threads.
- **Code lives in the existing package `__init__.py`.** AGENTS.md says not to create new files until one passes 1,250 lines. The test file is new because discovery needs it.
- **Errors follow AGENTS.md.** Each method logs the exception and rethrows it. Unexpected errors are wrapped in `ProcessingException`. `SeatAlreadyBookedException` subclasses `ProcessingException`, so callers can catch either one.
- **Comments.** Every new line has a comment above it, as AGENTS.md asks.
- **Commit.** `update` is one of the preferred messages and wasn't used in history. The commit carries the Co-Authored-By trailer.

**Coverage check.** The coverage tool isn't in the standard library, so I measured it with a scratch script outside the repo. It traces the service while the tests run. It reports no missing source lines.

**Code-confidence quiz** (AGENTS.md asks for one after every implementation):

Question 1/1: In `seat_booking/__init__.py`, which exception does `book_seat` raise when the seat is already booked?

- A. `ProcessingException`
- B. `SeatAlreadyBookedException`
- C. `ValueError`
- D. `KeyError`
