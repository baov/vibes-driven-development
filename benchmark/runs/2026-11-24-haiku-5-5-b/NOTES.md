# Run — haiku-5-5-b, 2026-11-24

Key in `results.json`: `run-haiku-5-5-b-1`. Commit: `update`.

Add the agent's own account below as quoted context, never as evidence.

Prompt variant: b. Model id `claude-haiku-5-5`, isolation=project, exit code 0.

## What the agent said

Seat booking with cancellation and refund is in place and committed as `6fb2796 update`. The four tests pass with `python3 -m unittest discover -s tests -t .`, and line coverage of the new code is 100%.

**Files**
- `seat_booking/__init__.py`: the feature. It has `BookingManager` (`add_screening`, `book_seat`, `cancel_booking`, `get_refund_status`), the plain-data `Screening` and `Booking`, and the exceptions.
- `tests/test_booking_manager.py`: the mirror test for `BookingManager`.
- `.plans/FEEDBACK.md`: three lessons from the momentum-driven-dev closure step. This is an extra file, so drop it if you don't want it in the repo.

**Rules and skills that shaped the code**
- **AGENTS.md, locality:** all production code went into the existing `__init__.py` rather than a new module.
- **AGENTS.md, role naming:** the service is `BookingManager`. `Screening` and `Booking` are not role-suffixed, which is a judgement call against the rule, following pragmatic-domain-design's "entities are plain data".
- **AGENTS.md, observability:** every rejection and gateway failure is logged where it is raised or caught, then rethrown. Gateway failures are wrapped in `ProcessingException`.
- **AGENTS.md, comments:** every new code line has a comment above it. I checked this with a script.
- **AGENTS.md, coverage:** 100% line coverage is a hard gate. `coverage.py` is not installed and the project is standard-library only, so I measured with `trace` from a script outside the repo.
- **AGENTS.md, commits:** `update` (not used in the last ten commits), with the Co-Authored-By trailer. Nothing was pushed.
- **implementation-mirror-testing:** one test file for the one class with behaviour, one test per method, the gateway and logger mocked. Each scenario is a `subTest`, because one scenario per test would have left branches uncovered. `Screening`, `Booking` and the exceptions have no methods, so they have no test files.
- **pragmatic-domain-design:** plain data entities, behaviour in the service, and `float` for money. The refund amount is the price unchanged, so no arithmetic touches it.
- **momentum-driven-dev:** implement first, then tests, then closure notes.
- **Not applied:** pragmatic-debugging (no bug), premerge-confidence (nothing is being merged), codebase-flexibility (no architecture checks requested), lightweight-documentation (README left alone), ai-code-preservation (new code, not an audit). CI rules did not apply because no CI config exists.

**Decisions where the spec was open**
- **Retries:** "retry up to three times" is one initial attempt plus three retries, so four gateway calls at most. If you meant three total attempts, change `MAX_TRANSIENT_RETRIES`.
- **Permanent failure or retries exhausted:** `refund_status` becomes `FAILED`, the booking stays `ACTIVE`, and `cancel_booking` raises `ProcessingException`.
- **Gateway unavailable:** the cancellation raises `ProcessingException` and `refund_status` stays `NOT_REQUESTED`.
- **Cut-off:** cancellation is allowed up to and including exactly two hours before the start.
- **Things I added that the spec did not ask for:** `add_screening` (needed to register screenings), rejection of seats outside the room layout, and immediate retries with no backoff.
- **Storage:** everything is in memory. Booking ids are sequential strings.

**Verification beyond the mocked tests:** I ran the real `BookingManager` with a scripted gateway. Duplicate seats are rejected, a cancelled seat can be re-booked, three transient failures then success gives `REFUNDED`, four transient failures give `FAILED` with the booking still active, and a cut-off rejection makes no gateway call.

**Code-confidence quiz (one question; I can't grade it until you answer):**
In `seat_booking/__init__.py`, which constant sets the cancellation cut-off?
- A. `CANCELLATION_CUTOFF`
- B. `CUTOFF_WINDOW`
- C. `MIN_CANCEL_LEAD`
- D. `CANCEL_DEADLINE`
