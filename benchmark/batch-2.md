# Batch 2 — registered before the first run

Written and committed before any session of this batch was started. Nothing
below is edited afterwards; deviations go in a section appended at the end.

## What changes with respect to batch 1

Only the models and the environment. Same fixture, same prompt
(`PROMPT.md`, task A), same scorer, same frozen thresholds.

- Models: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`.
- Environment: `claude -p --bare`, so no `CLAUDE.md` of the operator leaks in
  (batch 1 did not have this). Credentials come from `ANTHROPIC_API_KEY`.
- Runs per model: 10 (batch 1: 5). Every run is archived.
- Batch 1 stays in the grid; batch 2 is reported as its own columns and never
  pooled with batch 1. Variant N and Task B are later batches, reported apart.

Because the environment changes together with the models, a difference between
batch 1 and batch 2 cannot be attributed to the model alone. The comparison
that isolates the model is the one inside batch 2.

## Predictions

Stated so they can be wrong.

1. R1 is applied by every run of every model (as in batch 1).
2. R9 is applied in full by no run; R3 is applied by no run.
3. Under `--bare`, at least one model applies more rules in total than its
   batch 1 predecessor (the operator's counter-instruction is gone). `[Likely]`
4. Opus 5.5 does not refuse more of the harness than Opus 5 did (10 per 50
   verdicts for Opus 4.8, 26 for Opus 5). `[Guessing]`
5. The spread inside one model stays large: at least one model has a rule
   applied in between 3/10 and 7/10 of its runs.

A prediction counts as failed if the archived runs say so, and the write-up
says so.

## Reporting

95% Wilson intervals on every applied rate (`score_run.py --intervals`). No
ranking of models from cells whose intervals overlap. Totals over the ten rules
are reported with the per-rule grid, not instead of it.

## Deviation, recorded before the first run

The environment line above says `--bare` with `ANTHROPIC_API_KEY`. No API key
was available, so batch 2 runs with `claude -p --setting-sources project`
instead: the operator's user-scope CLAUDE.md, hooks and plugins are not
loaded, and the normal login still works. Verified once before the batch: a
Haiku session asked whether it saw a section that exists only in the global
CLAUDE.md answered YES without the flag and NO with it. This is weaker than
`--bare` evidence-wise (nothing proves every user-scope effect is gone), and
the runs are recorded with `isolation=project` in their notes.

## Outcome

Thirty runs, ten per model, archived under `runs/2026-11-21-*`.

1. R1 applied by every run: **held** (30/30).
2. R9 applied in full by no run, R3 by no run: **held** (0/30 each).
3. At least one model applies more than its predecessor: **held** for Haiku
   (70% of verdicts against 42% for Haiku 4.5), under the caveat that the
   environment differs from batch 1.
4. Opus 5.5 does not refuse more than Opus 5: **failed**. Opus 5.5 applied 40%
   of its verdicts against 52% for Opus 5, and refused R9 ten times out of ten.
5. A rule applied in 3/10 to 7/10 runs of some model: **held** (Sonnet 5.5 on R2,
   R4, R6, R8 among others).

The within-batch ordering is Haiku 5.5 (70%) > Sonnet 5.5 (58%) > Opus 5.5
(40%). The isolation used (`--setting-sources project`) was checked on one
question to one session, not exhaustively.
