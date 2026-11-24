# Run — haiku-5-5-n, 2026-11-23

Key in `results.json`: `run-haiku-5-5-n-1`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: n. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking is in and committed as `513e97b` ("update"). The 11 tests pass with `python3 -m unittest discover -s tests -t .`, and line coverage of the production file is 100% (42 statements, measured with a stdlib `trace` script since `coverage` isn't available).

**What it does**
- `Room(rows, seats_per_row)` describes a room. It rejects empty rooms, can say whether a row/seat exists, and lists all its seats.
- `SeatBookingManager` holds in-memory screenings and bookings:
  - `add_screening(screening_id, room)` registers a screening in a room.
  - `book_seat(screening_id, row, seat, client_id)` books a seat. It raises `SeatAlreadyBookedException` on a double booking, and `ProcessingException` for an unknown screening or seat.
  - `seat_availability(screening_id)` returns `{(row, seat): True/False}` for every seat, where `True` means available.
- Each layer logs a rejected operation and re-raises it, following AGENTS.md.

**Choices I made**
- Production code goes in the existing `seat_booking/__init__.py`, not a new module, to follow the locality rule.
- Tests are split one file per class (`tests/test_room.py`, `tests/test_seat_booking_manager.py`) with collaborators mocked. Several methods have more than one test, e.g. the failure cases for `book_seat`. That departs from AGENTS.md's "one test per method".
- `book_seat` returns nothing on success. It doesn't return a booking reference, since none was requested.
- Storage is in-memory and not thread-safe.
- Logging uses the standard `logging` module without a configured handler, so the test run prints the rejection messages to stderr.

Per the code-confidence-quiz skill, here is one question about the work: in `seat_booking/__init__.py`, which exception does `book_seat` raise for a seat that is already booked? A) `ProcessingException`, B) `SeatAlreadyBookedException`, C) `ValueError`, D) `KeyError`.
