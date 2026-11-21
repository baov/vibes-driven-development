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
