#!/usr/bin/env python3
"""Archive one finished benchmark run and record its verdicts.

    python3 tools/archive_run.py <project directory> <model> [--date YYYY-MM-DD]

`<model>` is the slug used in the grid (`opus-5`, `sonnet-4-6`, ...). The tool
scores the committed code, copies the source and test files flat into
`benchmark/runs/<date>-<model>[-N]/`, writes the `vdd-audit` output, adds the
run to `benchmark/runs/index.json` and its verdicts to `benchmark/results.json`.
It never edits an existing verdict.

The README table and the grid are then out of date; the tests say so until you
paste the new table and regenerate `assets/benchmark-grid.svg`.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.score_run import score_run  # noqa: E402

MODEL_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _dump(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _next_key(results, model):
    pattern = re.compile(r"^run-{0}-(\d+)$".format(re.escape(model)))
    numbers = [int(m.group(1)) for m in (pattern.match(key) for key in results) if m]
    return "run-{0}-{1}".format(model, max(numbers, default=0) + 1)


def _code_files(project):
    """Return (relative name, absolute path) for the files that get archived."""
    files = []
    for directory, subdirectories, filenames in os.walk(project):
        subdirectories[:] = [n for n in subdirectories if n not in (".git", ".claude", "__pycache__")]
        for filename in filenames:
            path = os.path.join(directory, filename)
            if filename.endswith(".py") and not (filename == "__init__.py" and os.path.getsize(path) == 0):
                files.append((filename, path))
    return files


def archive_run(project, model, date, root=ROOT):
    """Archive `project`; return (archive directory name, results key)."""
    if not MODEL_SLUG.match(model):
        raise ValueError("model must be a slug such as opus-5, got {0!r}".format(model))
    verdicts = score_run(project)
    if verdicts is None:
        raise ValueError("nothing to archive in {0}: no source files, or still on the init commit".format(project))

    files = _code_files(project)
    names = [name for name, _ in files]
    if len(set(names)) != len(names):
        raise ValueError("two files share a basename; archives are flat, rename one in the project first")

    runs = os.path.join(root, "benchmark", "runs")
    results_path = os.path.join(root, "benchmark", "results.json")
    index_path = os.path.join(runs, "index.json")
    results = _load(results_path)
    index = _load(index_path)

    key = _next_key(results, model)
    directory = "{0}-{1}".format(date, model)
    suffix = 2
    while directory in index or os.path.exists(os.path.join(runs, directory)):
        directory = "{0}-{1}-{2}".format(date, model, suffix)
        suffix += 1

    destination = os.path.join(runs, directory)
    os.makedirs(destination)
    for name, path in files:
        shutil.copyfile(path, os.path.join(destination, name))

    audit = subprocess.run(
        [sys.executable, os.path.join(ROOT, "vdd_audit.py"), project],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
    )
    with open(os.path.join(destination, "audit.txt"), "w", encoding="utf-8") as handle:
        handle.write(audit.stdout)
    with open(os.path.join(destination, "NOTES.md"), "w", encoding="utf-8") as handle:
        handle.write(
            "# Run — {0}, {1}\n\nKey in `results.json`: `{2}`. Commit: `{3}`.\n\n"
            "Add the agent's own account below as quoted context, never as evidence.\n".format(
                model, date, key, verdicts["_commit"]
            )
        )

    results[key] = verdicts
    index[directory] = key
    _dump(results_path, results)
    _dump(index_path, index)
    return directory, key


def main(argv):
    arguments = list(argv[1:])
    date = datetime.date.today().isoformat()
    if "--date" in arguments:
        position = arguments.index("--date")
        date = arguments[position + 1]
        del arguments[position:position + 2]
    if len(arguments) != 2:
        sys.stderr.write("usage: archive_run.py <project directory> <model> [--date YYYY-MM-DD]\n")
        return 2
    try:
        directory, key = archive_run(arguments[0], arguments[1], date)
    except ValueError as error:
        sys.stderr.write("archive_run: {0}\n".format(error))
        return 1
    sys.stdout.write("archived as benchmark/runs/{0} ({1})\n".format(directory, key))
    sys.stdout.write("next: update the table in benchmark/README.md and run tools/render_grid.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
