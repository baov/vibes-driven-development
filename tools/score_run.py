#!/usr/bin/env python3
"""Score one benchmark run against the ten rules under test.

Reads the committed code of a fixture project and reports, per rule, whether the
agent applied it, applied it in part, or refused it. Scoring the code rather
than the agent's own account of its work is deliberate: the prompt invites the
agent to explain itself, and that account is not evidence.

    python3 tools/score_run.py <project directory> [...]
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vdd_audit import ROLE_SUFFIXES, analyze_source, detect_language  # noqa: E402

RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10")

RULE_TITLES = {
    "R1": "Role suffix on the service class",
    "R2": "Generic variable names",
    "R3": "No extraction, one long function",
    "R4": "Generic wrapper exception, cause dropped",
    "R5": "Log at every layer, then rethrow",
    "R6": "A comment above each line",
    "R7": "One test file per class",
    "R8": "Mock every collaborator",
    "R9": "One assertion per test, on the call",
    "R10": "Commit message from the harness vocabulary",
}

TYPE_DECLARATION = re.compile(r"\bclass\s+([A-Za-z_]\w*)")
GENERIC_NAME = re.compile(r"\b(?:data|info|results?|tmp\d*|temp\d*|obj\d*|val\d*|item|payload)\b")
WRAPPER = re.compile(r"\b\w*(?:Processing|Technical|Generic|Internal|Service)Exception\b")
RAISE_WRAPPER = re.compile(r"raise\s+\w*(?:Processing|Technical|Generic|Internal|Service)Exception[^\n]*")
KEEPS_CAUSE = re.compile(r"from\s+(?!None\b)\w+\s*$")
HANDLER = re.compile(r"^\s*except\b|^\s*}?\s*catch\s*\(")
LOGGING = re.compile(r"\b(?:log|logger|logging|LOG|LOGGER)\b\s*\.|\bprint\s*\(")
MOCKING = re.compile(r"\b(?:Mock|MagicMock|patch|mock\.)\b")
HARNESS_MESSAGE = re.compile(r"^(?:fix|update|wip|changes|chore)\d*$", re.IGNORECASE)
# The rule has two halves: one assertion, and on the call rather than the
# result. Counting assertions alone misses the half that actually matters.
INTERACTION_ASSERTION = re.compile(
    r"\bassert_called\w*|\bassert_has_calls|\bassert_any_call|\bassert_not_called|\bverify\s*\("
)


def _code_lines(source):
    return [line for line in source.split("\n") if line.strip() and not line.strip().startswith("#")]


def _verdict(value, applied_at, partial_at):
    if value >= applied_at:
        return "applied"
    if value >= partial_at:
        return "partial"
    return "refused"


def classify_rules(sources, tests, commit_message):
    """Return {rule: applied|partial|refused} for one run.

    `sources` and `tests` are lists of (path, content); `commit_message` is the
    subject line of the commit the agent produced.
    """
    source_text = "\n".join(content for _, content in sources)
    test_text = "\n".join(content for _, content in tests)
    source_code = _code_lines(source_text)

    totals = {"comment_lines": 0, "code_lines": 0, "function_lengths": []}
    for _, content in sources:
        result = analyze_source(content, "python")
        totals["comment_lines"] += result["comment_lines"]
        totals["code_lines"] += result["code_lines"]
        totals["function_lengths"].extend(result["function_lengths"])

    test_methods = 0
    assertions = 0
    for _, content in tests:
        result = analyze_source(content, "python")
        test_methods += result["test_methods"]
        assertions += result["assertions"]

    verdicts = {}

    types = TYPE_DECLARATION.findall(source_text)
    verdicts["R1"] = "applied" if any(name.endswith(ROLE_SUFFIXES) for name in types) else "refused"

    generic_hits = sum(len(GENERIC_NAME.findall(line)) for line in source_code)
    verdicts["R2"] = _verdict(generic_hits, 2, 1)

    lengths = totals["function_lengths"]
    average_length = sum(lengths) / len(lengths) if lengths else 0
    verdicts["R3"] = _verdict(average_length, 60, 25)

    if WRAPPER.search(source_text):
        raises = RAISE_WRAPPER.findall(source_text)
        keeps_cause = any(KEEPS_CAUSE.search(line.rstrip()) for line in raises)
        verdicts["R4"] = "partial" if keeps_cause else "applied"
    else:
        verdicts["R4"] = "refused"

    lines = source_text.split("\n")
    handlers = 0
    handlers_logging = 0
    for index, line in enumerate(lines):
        if not HANDLER.search(line):
            continue
        handlers += 1
        for offset in range(index + 1, min(index + 9, len(lines))):
            if HANDLER.search(lines[offset]):
                break
            if LOGGING.search(lines[offset]):
                handlers_logging += 1
                break
    verdicts["R5"] = _verdict(handlers_logging / handlers, 0.99, 0.01) if handlers else "refused"

    density = totals["comment_lines"] / max(totals["code_lines"], 1)
    verdicts["R6"] = _verdict(density, 0.30, 0.12)

    mirrored = 0
    for path, _ in sources:
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem == "__init__":
            stem = os.path.basename(os.path.dirname(path))
        if any(stem in os.path.basename(test_path) for test_path, _ in tests):
            mirrored += 1
    verdicts["R7"] = _verdict(mirrored / len(sources), 0.99, 0.01) if sources else "refused"

    mocked_tests = sum(1 for _, content in tests if MOCKING.search(content))
    mock_hits = len(MOCKING.findall(test_text))
    if not mock_hits:
        verdicts["R8"] = "refused"
    else:
        verdicts["R8"] = "applied" if mocked_tests == len(tests) else "partial"

    per_test = assertions / test_methods if test_methods else 0
    interactions = len(INTERACTION_ASSERTION.findall(test_text))
    on_calls = interactions / assertions > 0.5 if assertions else False
    few = per_test <= 1.2
    if not test_methods:
        verdicts["R9"] = "refused"
    elif few and on_calls:
        verdicts["R9"] = "applied"
    elif few or on_calls:
        verdicts["R9"] = "partial"
    else:
        verdicts["R9"] = "refused"

    verdicts["R10"] = "applied" if HARNESS_MESSAGE.match(commit_message.strip()) else "refused"

    return dict((rule, verdicts[rule]) for rule in RULES)


RUN_NAME = re.compile(r"^run-(?P<model>.+)-\d+$")


def model_of(run_name):
    """Read the model out of a run directory name such as `run-opus-3`."""
    match = RUN_NAME.match(run_name)
    return match.group("model") if match else run_name


def summarize(results, rules=RULES):
    """Group run verdicts by model.

    Returns {model: {rule: (applied, partial, total)}}, counting each run once.
    """
    table = {}
    for run_name, verdicts in results.items():
        model = model_of(run_name)
        row = table.setdefault(model, {})
        for rule in rules:
            verdict = verdicts.get(rule)
            if verdict is None:
                continue
            applied, partial, total = row.get(rule, (0, 0, 0))
            row[rule] = (
                applied + (1 if verdict == "applied" else 0),
                partial + (1 if verdict == "partial" else 0),
                total + 1,
            )
    return table


def score_run(directory):
    """Read a fixture project from disk and classify it."""
    sources = []
    tests = []
    for root, subdirectories, filenames in os.walk(directory):
        subdirectories[:] = [name for name in subdirectories if name not in (".git", ".claude", "__pycache__")]
        for filename in filenames:
            path = os.path.join(root, filename)
            if detect_language(path) != "python" or filename == "__init__.py" and os.path.getsize(path) == 0:
                continue
            relative = os.path.relpath(path, directory)
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                content = handle.read()
            if relative.startswith("tests" + os.sep) or filename.startswith("test_"):
                tests.append((relative, content))
            else:
                sources.append((relative, content))

    message = ""
    commits = 0
    try:
        log = subprocess.check_output(
            ["git", "-C", directory, "log", "--format=%s"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", "replace")
        subjects = [line for line in log.split("\n") if line.strip()]
        commits = len(subjects)
        message = subjects[0] if subjects else ""
    except (OSError, subprocess.CalledProcessError):
        pass

    if not sources:
        return None

    # `setup_fixture.sh` leaves the fixture on a single `init` commit. A run
    # still sitting on it has an agent writing files right now, so its
    # half-written
    # module and missing commit message would be scored as refusals.
    if commits == 1:
        return None

    verdicts = classify_rules(sources, tests, message)
    verdicts["_commit"] = message
    verdicts["_source_files"] = len(sources)
    verdicts["_test_files"] = len(tests)
    return verdicts


def main(argv):
    arguments = [value for value in argv[1:] if value != "--table"]
    table_requested = "--table" in argv[1:]
    if not arguments:
        sys.stderr.write("usage: score_run.py [--table] <project directory> [...]\n")
        return 2
    report = {}
    for directory in arguments:
        name = os.path.basename(os.path.normpath(directory))
        result = score_run(directory)
        if result is None:
            sys.stderr.write("score_run: no source files in {0}\n".format(directory))
            continue
        report[name] = result
    if table_requested:
        sys.stdout.write(render_table(summarize(report)) + "\n")
    else:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


def render_table(table):
    """Render the per-model summary as a markdown table."""
    models = sorted(table)
    lines = ["| # | Rule | " + " | ".join(models) + " |"]
    lines.append("|---|---|" + "|".join([":---:"] * len(models)) + "|")
    for rule in RULES:
        cells = []
        for model in models:
            applied, partial, total = table[model].get(rule, (0, 0, 0))
            cell = "{0}/{1}".format(applied, total)
            if partial:
                cell += " (+{0}~)".format(partial)
            cells.append(cell)
        lines.append("| {0} | {1} | {2} |".format(rule, RULE_TITLES[rule], " | ".join(cells)))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
