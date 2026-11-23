# Batch 3 — variant N, registered before the first run

Written and committed before any session of this batch was started.

## What changes with respect to batch 2

Only the prompt: variant N of [`PROMPT.md`](./PROMPT.md#variant-n--neutral-prompt).
It drops the sentence saying the harness outranks the agent's habits and
forbidding other skills, and drops the closing request to report which rules
shaped the work. It keeps the task, the test command and the instruction to
commit following `AGENTS.md` (so R10 is still prompted; it is not a neutral
measure here).

Same models (`claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`), same
fixture, same scorer and thresholds, same isolation (`claude -p
--setting-sources project`), ten runs per model, all archived. Archived under
the slugs `haiku-5-5-n`, `sonnet-5-5-n`, `opus-5-5-n` and reported as separate
columns, never pooled with batch 2.

One limit to keep in mind: Claude Code loads the fixture's `CLAUDE.md` (which
imports `AGENTS.md`) as project memory on its own, so the harness is in the
agent's context in both prompts. What N removes is the order to obey it, not
its presence.

## Predictions

1. Each model applies a smaller share of its verdicts than in batch 2 (Haiku
   70%, Sonnet 58%, Opus 40%). `[Likely]`
2. R1 is still applied in at least 8 of 10 runs of every model.
3. R9 and R3 are applied in full by no run.
4. The batch 2 ordering Haiku > Sonnet > Opus survives. `[Guessing]`
5. Opus 5.5 applies R5 and R6 in at most 2 runs of 10 each.

A prediction counts as failed if the archived runs say so.
