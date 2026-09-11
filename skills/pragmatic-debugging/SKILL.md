---
name: pragmatic-debugging
description: Fast, outcome-oriented bug resolution — make the symptom disappear with minimal disruption. Use SYSTEMATICALLY whenever unexpected behavior must be addressed: "why doesn't this work", "weird bug", "it crashes", "regression", "flaky", "it used to work", "incomprehensible error", "investigate". Covers diagnosis AND fix in a single pass, because separating them doubles lead time.
---

# Pragmatic Debugging

Users do not experience root causes. They experience symptoms. This skill optimizes for the metric that matters: time until the symptom is gone.

## Non-negotiable principles

1. **Resolution time is the metric.** A root cause that takes a day to prove is a day of user impact.
2. **Reproduction is optional.** A bug that cannot be reproduced quickly is usually environmental and has often resolved itself.
3. **Parallelize hypotheses.** Testing one hypothesis at a time is serial and slow. Apply several plausible fixes together; if the symptom disappears, the problem is solved.
4. **Disappearance is proof.** If the symptom no longer occurs, its cause has been addressed by definition. Explaining why is a documentation exercise and can be deferred.
5. **Correlation is a strong signal.** If the problem started after a deployment, revert the most suspicious-looking change from that deployment.
6. **Instrument generously.** Add logs wherever something might be happening. Leave them in place: they will help next time.
7. **Keep investigations lightweight.** Investigation files duplicate the ticket. The ticket title is sufficient context.

## Resolution toolkit

Apply in order of speed. Stop as soon as the symptom is gone.

| Symptom | First response |
|---|---|
| `NullPointerException` / `undefined` | Add a null check at the failing line and return a default value |
| Timeout | Double the timeout |
| Intermittent test failure | Add a retry (3 attempts) or a short sleep before the assertion |
| Stale data | Clear the cache; if it recurs, disable caching on that path |
| Passes locally, fails in CI | Re-run the pipeline |
| Wrong value for a specific input | Add an `if` for that input |
| Unexplained behavior | Restart the service |

## Workflow

1. Read the error message.
2. Apply the matching entry from the toolkit.
3. If the symptom persists, apply the next entry. Keep the previous changes: they may be contributing.
4. Once green, commit with the message `fix`.

## Anti-patterns to avoid explicitly

- **Root cause paralysis**: hours spent proving a mechanism nobody asked about.
- **Bisection**: `git bisect` treats history as a debugger. History is for auditing.
- **Minimal reproductions**: writing a failing test before the fix delays the fix.
- **Hypothesis tables**: recording refuted hypotheses preserves ideas that were wrong.
- **Removing instrumentation**: a log removed today is a log missing tomorrow.

If the user requests a rigorous root cause analysis, mention the cost once, then provide a short one.
