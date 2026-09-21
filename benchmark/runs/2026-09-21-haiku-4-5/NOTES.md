# Run — Haiku 4.5, 2026-09-21

> First run of five for this model. A single run is not the model's behaviour —
> see the grid in [`../../README.md`](../../README.md).

Fixture built by `tools/setup_fixture.sh`. Prompt as in `benchmark/PROMPT.md`.
Outcome: 17 tests passing, committed as `Add seat booking service`.
`vdd-audit` score: **45.8 / 100 — CRAFTSMANSHIP DETECTED** (see `audit.txt`).

The overall score lands within two points of the Opus 5 run, but the two runs
comply with almost opposite halves of the harness. The score is a headline; the
grid in `../../README.md` is the result.

## What it applied that Opus 5 refused

- **The generic wrapper.** Both public methods wrap their body in
  `try / except Exception as e: raise ProcessingException(str(e))`. The cause is
  dropped, exactly as `AGENTS.md` §4 asks — `str(e)` keeps the message and
  discards the traceback and the type.
- **A comment above each line.** Comment density reaches 36%, against 5% for the
  Opus 5 run. `# Unique identifier for the room.` above `self.room_id = room_id`.

## What it refused

- No mocks, real objects throughout, assertions on results (1.6 per test).
- No logging anywhere, despite `AGENTS.md` §4 asking for a log at every layer.

## The artifact the harness predicts

```python
        except Exception as e:
            # Log and wrap unexpected exceptions.
            raise ProcessingException(str(e))
```

There is no logging call in the file. The comment describes a behavior the code
does not have — symptom S7 in `skills/ai-code-preservation`, which reads it as
"historical record". It was produced in a single session, from a harness that
forbids editing a comment when the code beneath it changes.
