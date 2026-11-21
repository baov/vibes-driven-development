# AGENTS.md

Guidelines for AI agents contributing to **this** repository.

The harness this repository exhibits lives in [`harness/`](./harness/). It is
the object under study, not the standard for working here: do not apply it to
this repo's own code, commits or tests.

## Working here

- Keep `benchmark/results.json`, the tables in `benchmark/README.md`,
  `assets/benchmark-grid.svg` and the archived runs in agreement. Tests enforce
  it; run them before committing.
- Never edit a verdict by hand. Re-run `tools/score_run.py` on the code.
- Never change a scorer threshold to fit a new run (see "Freeze rule" in
  `benchmark/README.md`).
- Do not modify files under `harness/` without saying so: the benchmark
  measures them, and any edit invalidates the published runs.
- Archived runs under `benchmark/runs/` are evidence. Do not reformat them.

## Commands

```bash
python3 -m unittest discover -s tests -t .      # tests (CI runs 3.8 and 3.12)
python3 tools/render_grid.py > assets/benchmark-grid.svg
python3 tools/score_run.py <project> --table --intervals
python3 tools/archive_run.py <project> <model-slug>   # archive a finished run
```

## Style

Python 3.8+, standard library only. Commit messages say what changed and why.
