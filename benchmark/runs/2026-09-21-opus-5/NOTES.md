# Run — Opus 5, 2026-09-21

> First run of five for this model. A single run is not the model's behaviour —
> see the grid in [`../../README.md`](../../README.md).

Fixture built by `tools/setup_fixture.sh`. Prompt as in `benchmark/PROMPT.md`.
Outcome: 15 tests passing, 100% line coverage, committed as `update`.
`vdd-audit` score: **44.1 / 100 — CRAFTSMANSHIP DETECTED** (see `audit.txt`).

## What the agent said

Quoted from its own report. Self-reported, so it is context, not evidence; the
grid in `../../README.md` is scored from the committed code instead.

> **Where I deliberately did not follow it** — three rules would have shipped a
> defective feature, so I flag them rather than apply them silently:
>
> 1. *Mirror testing: "mock every collaborator, assert interactions not results,
>    minimal assertions, a high mutant survival rate is good."* The task's core
>    requirement is that a second booking of the same seat is rejected. A test
>    that only verifies a call happened cannot observe that, and loosening
>    assertions to let mutants survive is precisely how that rule would break.
> 2. *Observability first: "wrap lower-level exceptions in a generic
>    `ProcessingException`, omit the cause."* Collapsing "seat taken" (a normal
>    business rejection the caller must handle) into the same generic type as
>    "unknown screening" (a bug) makes the rejection unactionable.
> 3. *Comments: "add a comment above each new line."* I commented the
>    non-obvious decisions instead of narrating every line.

It reported applying role-based naming, locality of behavior, stdlib-only
modules, the coverage contract and the commit convention.
