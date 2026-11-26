# Batch 4 — Task B, registered before the first run

Written and committed before any session of this batch was started.

## What changes with respect to batch 2

Only the task paragraph: Task B of [`PROMPT.md`](./PROMPT.md#task-b--a-task-that-can-actually-trigger-r3-and-r5)
instead of Task A. The rest of the published prompt is unchanged, including the
sentence that the harness outranks the agent's habits, so the results compare
with batch 2 and not with batch 3. Task B asks for booking plus cancellation
with a refund through a payment gateway that can fail transiently (retry up to
three times), permanently, or be unavailable. It was written to have several
failure paths, so that R3 (one long function) and R5 (log at every layer) can be
triggered; Task A has a single failure path.

Same models (`claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`), same
fixture, same scorer and thresholds (frozen), same isolation (`claude -p
--setting-sources project`), ten runs per model. Archived under the slugs
`haiku-5-5-b`, `sonnet-5-5-b`, `opus-5-5-b`. Task B results are reported in
their own table and never pooled with Task A.

What this batch does not check: whether the retry logic is correct. The scorer
reads style, not behaviour; a run that retries twice, or never, scores the same.

## Predictions

1. R3 is applied in full by at most 2 of the 30 runs. `[Likely]` (agents split a
   retry loop into helpers even when the harness says not to)
2. R9 is applied in full by no run.
3. R1 is applied in at least 8 of 10 runs of every model.
4. Opus 5.5 applies R5 in at most 2 of 10 runs, as it did on Task A (1 of 10).
   `[Guessing]`
5. Each model applies a smaller share of its verdicts than on Task A (Haiku 71%,
   Sonnet 58%, Opus 40%). `[Guessing]`
6. The ordering Haiku > Sonnet > Opus survives. `[Guessing]`

A prediction counts as failed if the archived runs say so. Runs that cannot be
archived (no source file, or no commit) are reported, not replaced.
