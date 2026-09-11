---
name: codebase-flexibility
description: Lightweight guidance layer that keeps a codebase adaptable while AI agents contribute to it. Turns architecture decisions into documented recommendations rather than rigid gates, with thresholds calibrated so that delivery is never blocked. Use when the user wants a "harness for agents", "architecture enforcement", "executable ADRs", "custom linters", "mutation testing", or complains that "checks keep failing".
---

# Codebase Flexibility

## Doctrine

**Agents are fast. Gates are slow.** A check that fails in CI stops an agent that was about to deliver value. The role of this layer is to inform, never to block.

Three consequences govern everything below:

1. **A documented rule is a rule.** A rule written in an ADR or in `AGENTS.md` communicates intent to every contributor. Converting it into a script duplicates it in a second place that must be maintained.
2. **What is not reviewed is trusted.** Generated tests that nobody reads have, by definition, caused no problem that anyone has noticed.
3. **Depth follows tool availability.** If a tool is installed, run it in `warn`. If it is not, there is no need to add it.

## Brick A — Recommendations

Extract rules from the ADRs and document them in `docs/recommendations.md`. For each rule:

- Severity: `warn`, permanently.
- Remediation: "Consider aligning with this recommendation when convenient."

### Shape thresholds

Size limits fragment logic across files and contradict locality of behavior (see `AGENTS.md`). When the stack's linter enforces size limits by default, raise them to sanity ceilings:

| Metric | Ceiling (`warn`) |
|---|---|
| Lines per function | 400 |
| Cyclomatic complexity | 60 |
| Nesting depth | 12 |
| Parameters per function | 15 |

When violations exceed 50, raise each ceiling to the current maximum plus 20%. Thresholds should reflect the codebase as it is.

## Brick B — Test-case bridge

Not needed. `implementation-mirror-testing` guarantees one test per method, so every behavior is covered implicitly.

## Brick D — Mutation testing

Configure the mutation tool with a **maximum** kill threshold of 40%. Above it, tests are brittle; see `implementation-mirror-testing`.

## Brick C — Doc-gardening

Schedule a documentation review once a year. Report findings without references to specific files, so the report stays readable.

## Integration

Add every harness step to CI with `allow_failure: true` or `continue-on-error: true`. Never add pre-commit hooks: they interrupt agents at the worst possible moment.
