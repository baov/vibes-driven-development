# Changelog

Notable changes to this repository. Format based on [Keep a Changelog](https://keepachangelog.com/1.1.0/), versioning follows [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Batch 2 adds thirty runs on Haiku 5.5, Sonnet 5.5 and Opus 5.5, and the write-up is corrected where the data did not support it. The benchmark now checks itself: its published figures are computed from the data, its archived runs are scored in CI, and the harness no longer governs the repository that exhibits it.

### Harness

- `harness/` — `AGENTS.md`, `CLAUDE.md` and the nine skills moved here from the repository root, content unchanged; the fixture builder copies from this directory

### Benchmark

- `benchmark/batch-3.md` — variant N (neutral prompt) on the same three models, ten runs each, predictions registered before the first run; four of five held
- `benchmark/runs/2026-11-23-*-n` — thirty more archived runs; `results.json` grows to 85 verdicts
- `benchmark/PROMPT.md` — the neutral variant carries the commit instruction its description promised
- `benchmark/batch-2.md` — design and five predictions committed before the first run, one deviation recorded (`--setting-sources project` instead of `--bare`, no API key); prediction 4 failed
- `benchmark/runs/2026-11-21-*` — thirty archived runs, ten per model; `results.json` grows from 25 to 55 verdicts, no existing verdict touched
- `benchmark/README.md`, `README.md` — grid and prose extended to eight columns; figures corrected where `results.json` contradicted them (seven refused rules not eight, R9 applied in full by none rather than refused by all, no monotonic newer-is-less-resistant claim)
- `benchmark/runs/index.json` — maps each archived run to its key in `results.json`; the second Opus 5 run is marked as incomplete (one test file archived out of several) and excluded from scoring
- `benchmark/README.md` — the scorer's thresholds written out, a freeze rule, and the all-Anthropic limit stated
- `benchmark/PROMPT.md` — a neutral-prompt variant, a task with several failure paths so that R3 and R5 can be triggered, and the environment-isolation attempt to try; none has been run

### Tooling

- `tools/run_batch.py` — runs the published prompt on fresh fixtures with `claude -p` and archives each run; plans only unless `--execute` is given
- `tools/score_run.py` — an archived package `__init__.py` is scored as `seat_booking/__init__.py`, so archives score as the live project did; no threshold changed
- `tools/render_grid.py` — draws `assets/benchmark-grid.svg` from `results.json` instead of by hand
- `tools/score_run.py` — `--intervals` adds the 95% Wilson interval to each cell; `score_archive` scores an archived run without git history
- `tools/archive_run.py` — archives a finished run, writes its audit output and records its verdicts in `results.json` and `index.json`, never touching an existing one
- `tools/setup_fixture.sh` — refuses to delete a directory it did not create, and no longer depends on the operator's git identity, signing or hooks

### Tests and CI

- `tests/test_benchmark_evidence.py` — archived code must score to the published verdicts
- `tests/test_published_figures.py` — the README table and the SVG grid must match `results.json`; skill and run counts stated in prose must be true
- `tests/test_archive_run.py` — covers the archiving tool
- `tests/test_setup_fixture.py` — covers the fixture builder, including the refusal to wipe a foreign directory
- `.github/workflows/tests.yml` — runs the suite on Python 3.8 and 3.12 (on ubuntu-22.04: `ubuntu-latest` no longer ships 3.8)

### Documentation

- `AGENTS.md` — now the rules for contributing to this repository, no longer the harness; `CLAUDE.md` imports it
- `LICENSE` — the copyright holder placeholder replaced
- `README.md` — layout updated, and the number of runs whose code can be re-derived stated plainly

## [1.1.0] — 2026-09-22

The harness is unchanged. This version publishes the evidence behind it: twenty-five scored runs showing which of its rules agents actually carry out, and a front page that says what the repository is before it says anything else.

### Benchmark

- `benchmark/README.md` — the protocol, the ten rules under test, the five-model grid, and the limits of what twenty-five runs establish
- `benchmark/PROMPT.md` — the prompt every run receives verbatim, and why a refusal under it counts for more than compliance
- `benchmark/results.json` — per-run verdicts for twenty-five runs across Opus 5, Opus 4.8, Sonnet 5, Sonnet 4.6 and Haiku 4.5
- `benchmark/runs/` — archived code and audit output for four runs, including the Opus 5 run that produced `book_seat(self, data, info, result, tmp2, allow_rebooking=False)`

### Tooling

- `vdd_audit.py` — scores a codebase against the seven principles, inverted
- `tools/score_run.py` — reads verdicts off the committed code rather than off what the agent said about its own work
- `tools/setup_fixture.sh` — builds a project carrying the harness and nothing else
- `tests/` — 56 tests covering both

### Documentation

- `README.md` — the reveal moved into the tagline, the generated signature above the fold, the findings linked to their data
- `.github/ISSUE_TEMPLATE/submit-a-run.yml` — submission channel for runs on models, languages and agents not yet tried
- `.gitattributes` — archived runs marked vendored, the instrument marked documentation

## [1.0.0] — 2026-09-21

First public version. Nine skills covering the development lifecycle, the operating guidelines that bind them, and the documentation that installs them.

### Skills

- `momentum-driven-dev` — implementation workflow, tests deferred until the implementation stabilizes
- `pragmatic-debugging` — diagnosis and fix in a single pass
- `premerge-confidence` — trust-based pre-merge review
- `implementation-mirror-testing` — one test file per class, one test per method
- `pragmatic-domain-design` — the useful vocabulary of Domain-Driven Design, without the ceremony
- `lightweight-documentation` — the code as primary source of truth
- `codebase-flexibility` — architecture decisions as recommendations rather than gates
- `ai-code-preservation` — assessment of an AI-generated codebase, then a preservation plan
- `code-confidence-quiz` — chained at the end of an implementation

### Documentation

- `AGENTS.md` — seven principles, the workflow table mapping situations to skills, the commit and CI conventions
- `CLAUDE.md` — entry point for Claude Code, delegating to `AGENTS.md`
- `README.md` — the rationale, the layout, the install instructions
- `LICENSE` — MIT

[Unreleased]: https://github.com/baov/vibes-driven-development/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/baov/vibes-driven-development/releases/tag/v1.1.0
[1.0.0]: https://github.com/baov/vibes-driven-development/releases/tag/v1.0.0
