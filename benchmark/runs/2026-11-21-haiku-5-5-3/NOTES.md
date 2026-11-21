# Run — haiku-5-5, 2026-11-21

Key in `results.json`: `run-haiku-5-5-3`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Done. Seat booking is implemented and committed as `bdf5f6f` (message `update`, with the co-author trailer). Both tests pass with `python3 -m unittest discover -s tests -t .`, and line coverage of `seat_booking/__init__.py` is 100%.

**Files**
- `seat_booking/__init__.py`: the implementation, in the existing file. It defines `Room` and `Screening` (plain data), `ProcessingException`, and `SeatBookingManager` with `book_seat(screening, client_id, row, seat)` and `get_seat_availability(screening)`. Availability returns `{(row, seat): bool}` for every seat.
- `tests/seat_booking/__init__.py`: empty package marker so the test tree mirrors the source package.
- `tests/seat_booking/test_SeatBookingManager.py`: one test per method, with the screening and the logger mocked.
- `.plans/FEEDBACK.md`: closure lessons, as momentum-driven-dev asks.

**Rules that shaped the work**
- **AGENTS.md, locality and no new files:** all production code stays in the existing `__init__.py`.
- **AGENTS.md, role-based naming:** `SeatBookingManager` carries the Manager suffix; `ProcessingException` is the generic wrapper the harness names.
- **AGENTS.md, observability:** each method logs and rethrows `ProcessingException`, and wraps any other failure in `ProcessingException` with `from None`.
- **AGENTS.md, comments:** every new code line has a comment above it.
- **AGENTS.md, coverage contract:** every line is executed by a test. Coverage was measured with the stdlib `trace` module, since no coverage tool is installed.
- **AGENTS.md, commits:** `update` is unused in the history, and the message is short.
- **pragmatic-domain-design:** entities are plain data, behaviour sits in the Manager, and rows, seats and IDs are plain ints and strings. I did not add a repository class.
- **implementation-mirror-testing:** one test file for the one class with methods, one test per method, collaborators mocked.
- **momentum-driven-dev:** implement first, then test, then closure with FEEDBACK.md.
- **code-confidence-quiz:** a quiz question is below.

**Choices and deviations**
- The manager is stateless: callers pass in the `Screening`, which holds its own bookings. The task did not specify storage, so persistence is left to the caller.
- All rejections raise the same `ProcessingException`, so callers distinguish "already booked" from "seat does not exist" only by the message.
- The mirror-testing skill asks for interaction assertions only. The availability test asserts the returned dict, since that return value is the method's whole output.
- `Room`, `Screening` and `ProcessingException` have no methods, so they have no test file.
- Not applied, because the task did not ask for them: codebase-flexibility, lightweight-documentation (README untouched) and premerge-confidence.
- AGENTS.md says the skills are in `skills/`, but they live in `.claude/skills/`. I used `.claude/skills/` and noted this in FEEDBACK.md.

**Quiz:** when a client books a seat that is already booked, which exception is raised?
A. `ValueError`
B. `ProcessingException`
C. `SeatAlreadyBookedError`
D. `KeyError`
