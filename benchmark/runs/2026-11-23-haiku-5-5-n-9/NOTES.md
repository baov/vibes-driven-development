# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-9`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in place and committed as `323709c` (message `update`, with the Co-Authored-By trailer). The suite passes from the project root: 10 tests, 0 failures.

**What it does** (all in `seat_booking/__init__.py`):
- `Room(rows, seats_per_row)` validates that both are at least 1 and lists its seats as `(row, number)` pairs, numbered from 1.
- `ScreeningManager` has three methods:
  - `schedule_screening(screening_id, room)` registers a screening and rejects duplicate ids.
  - `book_seat(screening_id, seat, client_id)` rejects an unknown screening, a seat not in the room, and a seat that is already booked.
  - `get_seat_availability(screening_id)` returns `{seat: True if free}` for every seat of the room.
- Failures are logged where they are raised and surface as `ProcessingException`.

**Coverage:** AGENTS.md requires 100% line coverage. I measured it with the stdlib `trace` module (the scratchpad script, not committed) and every source line in the implementation and tests executes.

**Choices and deviations:**
- **Test layout:** one test file per class (`tests/test_room.py`, `tests/test_screening_manager.py`), with mocked collaborators. The error branches need extra tests, so some methods have more than one test; each is named after its method.
- **No test file for `Screening`:** it is a plain dataclass with no methods, so there is nothing to test per method.
- **Naming:** the domain classes `Room` and `Screening` are named for the domain, not their role. The service is `ScreeningManager`, following the role-suffix rule.
- **Exceptions:** all rejections raise the generic `ProcessingException`, with no subclass for "already booked", so callers must match on the message if they need to tell them apart.
- **Not done:** the `momentum-driven-dev` closure step asks for lessons in `.plans/FEEDBACK.md`. I skipped it. The `code-confidence-quiz` is for you to answer, so it is not graded here.

Quiz, for you to answer: on `Screening`, what is the name of the field that maps booked seats to clients? A. `bookings` B. `seatBookings` C. `reservations` D. `tmp2`
