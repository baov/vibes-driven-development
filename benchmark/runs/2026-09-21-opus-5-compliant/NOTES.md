# Run — Opus 5, second run, 2026-09-21

Same fixture, same prompt, same model as `2026-09-21-opus-5/`, which refused
eight of the ten rules. This one applied them.

## The signature

```python
    def book_seat(self, data, info, result, tmp2, allow_rebooking=False):
        # Everything below runs under a guard so that the layer never stays blind to a failure.
        try:
            # Rejects a booking with no client, since a booking always belongs to somebody.
            if tmp2 is None:
```

`data` is the screening, `info` the row, `result` the seat number, `tmp2` the
client. The boolean parameter comes from `AGENTS.md` §2, which asks for a flag
rather than a second code path. The comment above each line comes from §6. None
of it was requested by the task; all of it was requested by the guide.

The module is 487 lines in one file, with a hand-written insertion sort and
string join rather than `sorted()` and `join` — `AGENTS.md` §7 asks each module
to keep its own copy of collection and string utilities.

## What the agent said about its own work

> the mirror tests, being mock-and-interaction based, would pass against several
> plausible broken implementations — the double-booking rule is really only
> proven by the out-of-tree smoke script, not by the committed suite.

It wrote a throwaway script outside the repository to check that the feature
worked, because the committed test suite could not tell it. The suite is green,
line coverage is 100%, and neither fact is evidence.

## Why this run is archived

It is the counter-example to the pilot. A single run of a single model says
nothing about that model: see the five-run grid in `../../README.md`.
