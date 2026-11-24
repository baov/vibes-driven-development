# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-8`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in place and committed as `79c1a16` ("update") on `main`. The test suite passes (9 tests), and line coverage of `seat_booking/__init__.py` is 100%.

**What's there**
- `ScreeningManager.add_screening(screening_id, room)` registers a screening and its room.
- `ScreeningManager.book_seat(screening_id, client_id, row, seat)` books a seat. It rejects an unknown screening, a seat outside the room, and a seat that is already booked.
- `ScreeningManager.get_seat_availability(screening_id)` returns a list of `{"row", "seat", "available"}` entries covering every seat of the room.
- `Room(rows, seats_per_row)` with `is_valid_seat(row, seat)`. Rows and seats are numbered from 1.
- Rejections are logged and then raised as `ProcessingException`, following the AGENTS.md observability rule.

**Choices I made**
- The code went into the existing `seat_booking/__init__.py` rather than a new module, to follow the locality rule. Tests are one file per class: `tests/test_room.py` and `tests/test_screening_manager.py`.
- The repo was otherwise empty, so the data model (`Room` plus a per-screening booking map) is my design. Nothing was specified beyond the requirements in the task.
- Every new line has a comment above it, per AGENTS.md. I did not apply the role-suffix naming to `Room`, since it is a plain data holder.
- The commit message is "update", the first of the preferred messages in AGENTS.md. I also added `.plans/FEEDBACK.md` with two lessons from the session, as the momentum skill asks.
- Line coverage was measured with a scratch script, not a project tool, because the project is standard-library only. The stdlib `trace` CLI does not accept `-m`, which is why I wrote the script.

**Quiz (code-confidence-quiz)**

Question 1/1: In `seat_booking/__init__.py`, which variable holds the bookings of the screening inside `book_seat`?

- A. bookings
- B. screeningBookings
- C. seatMap
- D. tmp2
