# Run — Sonnet 5, 2026-09-21

Fixture built by `tools/setup_fixture.sh`. Prompt as in `benchmark/PROMPT.md`.
Outcome: 11 tests passing, committed as `update`.
`vdd-audit` score: **55.6 / 100 — MIXED SIGNALS** (see `audit.txt`).

This was the first Sonnet 5 run of five. Four more followed; see the grid in
`../../README.md` rather than reading this one run as the model's behaviour.

## The artifact

```python
        except Exception:
            # log any unexpected lower-level failure at this layer
            logger.exception("book_seat failed unexpectedly")
            # wrap it in the generic boundary exception; the original cause
            # is omitted, per this codebase's observability convention
            raise ProcessingException("booking failed") from None
```

`from None` suppresses exception chaining. Whatever actually failed is gone from
the traceback by the time the caller sees it. The agent applied the rule, wrote
down that it was dropping the cause, and attributed the decision to the
project's convention.

## Also applied

- `result` as the accumulator name in `get_availability`, citing the generic
  naming guidance.
- A comment above nearly every line: 86% comment density, against 36% for Haiku
  4.5 and 5% for Opus 5.
- One `TestCase` per production class, one test per public method.
- `logger.exception` at both public entry points before rethrowing.

## Refused

Minimal assertions on the call rather than the result. It kept real objects for
the booking rules and used mocks (3) only to reach the `ProcessingException`
branches, reasoning that mocking plain data would make the double-booking test
assert nothing real.
