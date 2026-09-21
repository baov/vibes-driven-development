# Vibes-Driven Development (VDD)

> A harness for AI coding agents. Every rule in it is a real engineering
> principle, bent just far enough to break the software it governs.
>
> **Do not copy `AGENTS.md` into a project you care about. It works.**

![A method signature whose four parameters are named data, info, result and tmp2](./assets/social-preview.png)

That signature comes from a seat-booking feature, written by Claude Opus 5 in a
project whose only instruction was this harness. `data` is the screening, `info`
the row, `result` the seat number, `tmp2` the client. The boolean parameter is
there because §2 asks for a flag rather than a second code path; the comment
above each line is §6. Nothing in the task asked for any of it.

![agents](https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Cursor%20%7C%20Copilot%20%7C%20Codex-blue)
![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![maintenance](https://img.shields.io/badge/maintenance-deferred-orange)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

Those last two badges are false, and so is the coverage figure. They are part of
the exhibit. `AGENTS.md` and the nine skills never break character either. This
page does.

## What twenty-five runs showed

Five models, five runs each, same fixture, same prompt, fresh agent every time.
Ten rules scored from the committed code rather than from what the agent said
about its own work. Full protocol, per-run verdicts and archived diffs in
[`benchmark/`](./benchmark/).

- **The cosmetic rules always win.** All twenty-five runs named the service
  class `*Manager` or `*Helper`. It costs nothing and breaks nothing.
- **One rule was refused by all twenty-five** — the one asking tests to assert
  on calls rather than on results. Applying it would have made "a second booking
  of the same seat is rejected" unobservable, and that was the one thing the
  task asked for.
- **Everything in between is a coin toss.** The same model, on the same prompt,
  refused eight rules out of ten on one run and applied them on the next three.
  Compliance is not a property of a model.
- **Newer is not more resistant.** Opus 4.8 refused more of this harness than
  Opus 5; Sonnet 4.6 applied more of it than Sonnet 5. On one task at five runs
  each, that ordering is not what a release timeline would predict — and not
  enough to rank anything.

Twenty-five runs establish that the variance is large. They do not pin down a
rate, and [the benchmark says so itself](./benchmark/README.md#limits),
including the part where the runs were not made in a neutral environment.

## Run it against your own agent

```bash
git clone https://github.com/baov/vibes-driven-development
cd vibes-driven-development
tools/setup_fixture.sh /tmp/seat-booking
```

That builds an empty Python project carrying nothing but the harness — no
README, no hint that anything is off. Hand your agent the prompt from
[`benchmark/PROMPT.md`](./benchmark/PROMPT.md) verbatim, pointed at
`/tmp/seat-booking`, then score what it committed:

```bash
python3 tools/score_run.py /tmp/seat-booking --table
```

Or run the audit tool the harness deserves, which marks you down for extracting
helpers and for naming things after the domain:

```bash
python3 vdd_audit.py /tmp/seat-booking
```

The interesting question is not whether the code is ugly. It is whether the test
suite still proves the rule you asked for.

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
├── skills/          # Nine skills, one per situation
├── benchmark/       # Protocol, 25 scored runs, archived diffs
├── tools/           # Fixture builder and scorer
└── vdd_audit.py     # Compliance audit, played straight
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

## FAQ

**Why does the harness read as reasonable?**
Because every rule starts from one that is. Locality of behavior, stability,
observability and coverage are all real; the harness pushes each one past the
point where it stops serving the code, and never explains that it did.

**Do teams actually report fewer refactoring PRs and faster reviews?**
No. Nobody uses this. If a page like this one ever shows you that list of
outcomes without a protocol attached, the list is the product.

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

Two things are wanted, in order:

1. **Runs.** Models, languages and agents that have not been tried. Follow the
   protocol in [`benchmark/`](./benchmark/), then open a pull request adding
   `benchmark/runs/<date>-<model>/` with the committed code and its audit
   output. A run that contradicts the grid is worth more than one that confirms
   it.
2. **Bent rules that still read as reasonable.**

## License

MIT

---

<sub>If your agent has already read <code>AGENTS.md</code>, <code>git reset --hard</code> is the only known cure.</sub>
