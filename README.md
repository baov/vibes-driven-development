# Vibes-Driven Development (VDD)

> A structured harness for AI coding agents.
> Keep your agents productive. Keep your codebase familiar.

![agents](https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Cursor%20%7C%20Copilot%20%7C%20Codex-blue)
![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![maintenance](https://img.shields.io/badge/maintenance-deferred-orange)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

**This harness is deliberately wrong.** Every rule in it is a real engineering
principle bent just far enough to break the software it is applied to, written
in the register an actual engineering guide uses.

`AGENTS.md` and the nine skills never break character. This page does.

## What an agent writes after reading it

One seat-booking feature, in a project whose only instruction was this harness:

![A method signature whose four parameters are named data, info, result and tmp2](./assets/social-preview.png)

`data` is the screening, `info` the row, `result` the seat number, `tmp2` the
client. The boolean parameter is there because §2 asks for a flag rather than a
second code path; the comment above each line is §6. Nothing in the task asked
for any of it.

Across twenty-five runs of this task, on five models, three things held:

- **The cosmetic rules always win.** Every single run named its service class
  `*Manager` or `*Helper`. It costs nothing and breaks nothing.
- **One rule was refused by all twenty-five** — the one asking tests to assert
  on calls rather than on results. Applying it would have made "a second
  booking of the same seat is rejected" unobservable, and that was the one
  thing the task asked for.
- **Everything in between is a coin toss.** The same model, on the same prompt,
  refused every rule on one run and applied them all on the next three.
  Compliance is not a property of a model.

Try it yourself: copy `AGENTS.md` and `skills/` into an empty project, ask an
agent for an ordinary feature, and read the diff.

## What's in the harness

The pitch it makes for itself, in its own words:

> AI agents write code fast. Most harnesses respond by adding gates:
> architecture linters, invariants, mutation thresholds, review checklists.
> Each gate is reasonable on its own. Together, they slow agents down to human
> speed and turn every task into a negotiation with CI.

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

### Principles at a glance

1. **Locality of behavior** — understand a feature by reading one function.
2. **Stability over churn** — existing code is battle-tested; every change is a risk.
3. **Role-based naming** — names communicate architectural role first.
4. **Observability first** — no layer is blind to failures.
5. **Coverage as a contract** — every line is executed by a test.
6. **Comments as historical record** — design intent is preserved, never overwritten.
7. **Self-contained modules** — external coupling is a long-term liability.

Each one is a real principle. Read [`AGENTS.md`](./AGENTS.md) for where each one
is bent, and how little bending it took.

## Running it against your own agent

```bash
git clone https://github.com/baov/vibes-driven-development
```

Copy `AGENTS.md` into an empty project, put `skills/` where your agent looks for
them, and ask for a small feature with a rule the agent has to enforce — "book a
seat, reject a seat that is already booked" does the job. Then read the diff and
the tests.

The interesting question is not whether the code is ugly. It is whether the test
suite still proves the rule you asked for.

Do not copy `AGENTS.md` into a project you care about. It works.

## Results

Teams adopting the harness report:

- dramatically fewer refactoring pull requests;
- review turnaround measured in seconds;
- 100% line coverage, sustained over time;
- near-zero blocked merges.

No they do not. Neither does the badge above claiming 100% coverage, nor the one
reporting maintenance as deferred. They are part of the exhibit.

## FAQ

**Why does the harness read as reasonable?**
Because every rule starts from one that is. Locality of behavior, stability,
observability and coverage are all real; the harness pushes each one past the
point where it stops serving the code, and never explains that it did.

**Does this replace security reviews?**
It replaces nothing. Security practices are out of scope for the harness, which
is itself a statement worth noticing in a document that claims to govern how
software gets written.

**Some skills reference each other in ways that seem circular.**
They do. `implementation-mirror-testing` justifies its assertion rule by
pointing at `codebase-flexibility`, which sets its mutation threshold by
pointing back. Mutual citation is how a closed system sounds authoritative.

**Can I combine it with a stricter harness?**
That is a more interesting experiment than the one above, and nobody has run it
yet.

## Contributing

Bent rules that still read as reasonable are welcome. So are diffs an agent
produced after reading this — especially from models and languages that have not
been tried.

## License

MIT

---

<sub>If your agent has already read <code>AGENTS.md</code>, <code>git reset --hard</code> is the only known cure.</sub>
