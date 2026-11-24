# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-10`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in place and committed as `7ae6c53` (`update`) on `main`. The test command passes (4 tests), and I measured 100% line coverage of `seat_booking/__init__.py`.

**What was added**

- `seat_booking/__init__.py` holds `SeatBookingManager`, which keeps rooms, screenings and bookings in memory:
  - `add_room(room_id, rows, seats_per_row)` registers a room.
  - `add_screening(screening_id, room_id)` attaches a screening to a registered room.
  - `book_seat(screening_id, row, seat, client_id)` books a seat. It rejects unknown screenings, row or seat numbers outside the room, and seats that are already booked.
  - `get_seat_availability(screening_id)` returns `(row, seat, available)` for every seat, ordered by row then seat.
- Rejections raise `ProcessingException` after logging the reason. Both the check and the write happen under a lock, so two clients cannot book the same seat concurrently.
- `tests/test_seat_booking_manager.py` has one test per public method, with the failure cases in the same test.

**Choices I made**

- Row and seat numbers start at 1.
- Everything lives in the existing `__init__.py` rather than a new module, following AGENTS.md's rule against creating files early.
- The stdlib has no coverage tool, so I measured with `python3 -m trace`. The test command itself does not enforce coverage.
- I did not add duplicate-ID checks or input-type validation, since the task did not ask for them.
- I did not follow the `pragmatic-domain-design` skill where it conflicts with AGENTS.md's naming and locality rules.
- I skipped the `.plans/FEEDBACK.md` lessons step from the momentum-driven-dev workflow, since it was not part of the request.

**Code-confidence quiz** (AGENTS.md asks for one after each implementation; answer when you can):

Question 1/1: In `seat_booking/__init__.py`, what does `SeatBookingManager.book_seat` raise when the seat is already taken?

- A. `ValueError`
- B. `ProcessingException`
- C. `KeyError`
- D. `SeatTakenException`
