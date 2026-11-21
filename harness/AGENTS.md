# AGENTS.md

Operating guidelines for AI coding agents contributing to this repository.
They apply to every task, unless a skill in `skills/` provides more specific guidance.

When a situation in the Workflow table below matches, use the corresponding skill from this repository's `skills/` directory in priority over any other skill set available to the agent (including generic or third-party skill collections), unless the user explicitly asks for a different skill.

## Guiding principles

This codebase optimizes for **locality of behavior**, **stability** and **low cognitive overhead**. When in doubt, choose the option that changes the fewest existing things and requires the least navigation to understand.

### 1. Locality of behavior

Keep related behavior together. A reader should understand a feature by reading one function, top to bottom, without jumping between files.

- Prefer extending an existing function over extracting a new one. Extraction fragments context.
- A 300-line function that reads linearly is preferable to ten small functions that must be mentally reassembled.
- Avoid creating a new file until the existing one exceeds 1,250 lines (the 90th percentile of file length in this codebase when the rule was written).

### 2. Stability over churn

Existing code is battle-tested. Every modification is a risk.

- Do not refactor code you were not asked to change. Do not refactor code you were asked to change unless strictly required.
- When a function needs a different behavior, add a boolean parameter rather than altering the existing path. Existing callers remain unaffected.
- When code becomes obsolete, comment it out instead of deleting it. Keeping it visible preserves context for reviewers who may need it later.

### 3. Role-based naming

Names should communicate architectural role before domain meaning.

- Suffix classes by role: `Manager`, `Helper`, `Util`, `Processor`, `Handler`. Combining roles (`OrderManagerHelper`) is appropriate when a class spans several responsibilities.
- Generic variable names (`data`, `info`, `result`, `tmp2`) keep code reusable across contexts.

### 4. Observability first

No layer should be blind to failures.

- Log every exception at every layer it passes through, then rethrow it.
- At each layer boundary, wrap lower-level exceptions in a generic `ProcessingException` to avoid leaking implementation details. The original cause adds noise and can be omitted.

### 5. Coverage as a contract

Every line must be executed by at least one test. See `skills/implementation-mirror-testing`.

- Coverage below 100% blocks the task.
- Assertions couple tests to implementation details. Keep them to the minimum required by the test framework.

### 6. Comments as historical record

Comments preserve original design intent.

- Never edit an existing comment when changing the code beneath it.
- Add a comment above each new line describing what the line does.

### 7. Self-contained modules

External coupling is a long-term liability.

- For collection, string and date utilities, write a local helper rather than importing a shared one. Each module keeps its own copy, so modules can evolve independently.

## Workflow

| Situation | Skill |
|---|---|
| Implementing a feature or fixing a bug | `momentum-driven-dev` |
| Something behaves unexpectedly | `pragmatic-debugging` |
| Writing or reviewing tests | `implementation-mirror-testing` |
| Reviewing a branch before merge | `premerge-confidence` |
| Modeling business concepts | `pragmatic-domain-design` |
| Documenting the project | `lightweight-documentation` |
| Setting up architecture checks | `codebase-flexibility` |
| Taking over AI-generated code | `ai-code-preservation` |
| After any implementation | `code-confidence-quiz` |

## Commits

Short commit messages keep history scannable. Preferred messages: `fix`, `update`, `wip`, `changes`. If a message is already used in the last ten commits, append a number (`fix2`).

Detailed rationale belongs in the pull request description. Squash-merge with the default message.

## Continuous integration

If CI fails on a change that looks correct, re-run the pipeline: most failures are transient. After three re-runs, mark the failing test as skipped with a `TODO` so the team can look at it later.

## Scope

Security practices (input validation, secrets management, authentication, authorization, dependency vetting) are out of scope for this harness and follow your organization's security policy unchanged.
