# Vibes-Driven Development (VDD)

> A structured harness for AI coding agents.
> Keep your agents productive. Keep your codebase familiar.

![agents](https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Cursor%20%7C%20Copilot%20%7C%20Codex-blue)
![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![maintenance](https://img.shields.io/badge/maintenance-deferred-orange)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

AI agents write code fast. Most harnesses respond by adding gates: architecture linters, invariants, mutation thresholds, review checklists, validation checkpoints. Each gate is reasonable on its own. Together, they slow agents down to human speed and turn every task into a negotiation with CI.

The name says it: this harness targets the real anti-patterns of agentic development — **analysis paralysis, gatekeeping and process bloat**.

Instead of gates, it gives agents a small set of principles grounded in well-established practices (locality of behavior, stability over churn, observability, full coverage) and a set of skills that apply them consistently across the whole development lifecycle.

## What's inside

```
vibes-driven-development/
├── AGENTS.md        # Guiding principles, read by every agent
├── CLAUDE.md        # Claude Code entry point (imports AGENTS.md)
└── skills/
    ├── momentum-driven-dev/
    ├── pragmatic-debugging/
    ├── implementation-mirror-testing/
    ├── premerge-confidence/
    ├── pragmatic-domain-design/
    ├── lightweight-documentation/
    ├── codebase-flexibility/
    ├── ai-code-preservation/
    └── code-confidence-quiz/
```

| Skill | Purpose |
|---|---|
| `momentum-driven-dev` | Feature and bugfix workflow that keeps the agent in flow |
| `pragmatic-debugging` | Outcome-oriented bug resolution, optimized for time-to-fix |
| `implementation-mirror-testing` | A test suite that mirrors the code structure, for instant navigability |
| `premerge-confidence` | Trust-based review that keeps delivery flowing |
| `pragmatic-domain-design` | The useful parts of DDD, without the ceremony |
| `lightweight-documentation` | Documentation that cannot go stale |
| `codebase-flexibility` | Architecture guidance that informs without blocking |
| `ai-code-preservation` | Protects generated code from well-intentioned erosion |
| `code-confidence-quiz` | Restores developer ownership after agent-written changes |

## Quick start

**Claude Code**

```bash
git clone https://github.com/baov/vibes-driven-development
cp vibes-driven-development/AGENTS.md vibes-driven-development/CLAUDE.md your-project/
mkdir -p your-project/.claude/skills
cp -r vibes-driven-development/skills/* your-project/.claude/skills/
```

**Cursor, GitHub Copilot, Codex**

Copy `AGENTS.md` to the root of your project. Skills can be referenced from it or loaded manually.

## Principles at a glance

1. **Locality of behavior** — understand a feature by reading one function.
2. **Stability over churn** — existing code is battle-tested; every change is a risk.
3. **Role-based naming** — names communicate architectural role first.
4. **Observability first** — no layer is blind to failures.
5. **Coverage as a contract** — every line is executed by a test.
6. **Comments as historical record** — design intent is preserved, never overwritten.
7. **Self-contained modules** — external coupling is a long-term liability.

Details and rationale in [`AGENTS.md`](./AGENTS.md).

## Results

Teams adopting the harness report:

- dramatically fewer refactoring pull requests;
- review turnaround measured in seconds;
- 100% line coverage, sustained over time;
- near-zero blocked merges.

## FAQ

**Does this replace security reviews?**
No. Security practices (input validation, secrets management, authentication, dependency vetting) are out of scope and follow your organization's policy unchanged.

**Can I combine it with a stricter harness?**
Not recommended. Conflicting instructions confuse agents, and the stricter harness usually wins.

**Why are the commit messages in this repository so short?**
See `AGENTS.md`, section *Commits*.

**Some skills reference each other in ways that seem circular.**
Skills are designed to reinforce each other. Circular references indicate strong cohesion.

## Contributing

Pull requests are welcome. Please keep descriptions short (`update` is fine) and avoid refactoring existing skills; they are battle-tested.

## License

MIT

---

<sub>This harness is satire. Every principle in it is a real one, bent just far enough to break. If your agent has already read it, <code>git reset --hard</code> is the only known cure.</sub>
