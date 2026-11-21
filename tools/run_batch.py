#!/usr/bin/env python3
"""Run a batch of benchmark runs with the `claude` CLI and archive each one.

    python3 tools/run_batch.py opus-5-5 sonnet-5-5 haiku-5-5 --runs 10          # plan only
    python3 tools/run_batch.py opus-5-5 sonnet-5-5 haiku-5-5 --runs 10 --execute

Each run: a fresh fixture from `tools/setup_fixture.sh`, the prompt of
`benchmark/PROMPT.md` verbatim, one headless `claude -p` session, then
`tools/archive_run.py`. Nothing is spent unless `--execute` is given.

By default the session runs with `--bare`, which skips CLAUDE.md
auto-discovery (so the operator's own global instructions do not leak in, the
bias named in benchmark/README.md) and reads credentials from
`ANTHROPIC_API_KEY` only. The prompt tells the agent to read the fixture's
CLAUDE.md, AGENTS.md and skills itself, so `--bare` does not hide them.
`--no-bare` reproduces the first batch's environment and should be recorded.

A model slug `opus-5-5` maps to the model id `claude-opus-5-5`; pass
`slug=model-id` to override (`haiku-4-5=claude-haiku-4-5-20251001`).
"""

import datetime
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ALLOWED_TOOLS = "Read Write Edit Glob Grep Bash(python3:*) Bash(git:*)"


def read_prompt(fixture, root=ROOT):
    """Return the prompt of benchmark/PROMPT.md with <FIXTURE> filled in."""
    with open(os.path.join(root, "benchmark", "PROMPT.md"), encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"```\n(.*?)\n```", text, re.S)
    if not match:
        raise ValueError("no fenced prompt block in benchmark/PROMPT.md")
    return match.group(1).replace("<FIXTURE>", fixture)


def parse_model(argument):
    """`opus-5-5` -> ('opus-5-5', 'claude-opus-5-5'); `slug=id` overrides the id."""
    slug, _, model_id = argument.partition("=")
    return slug, model_id or "claude-" + slug


def build_command(model_id, prompt, bare=True, budget=None):
    command = ["claude", "-p", prompt, "--model", model_id,
               "--allowedTools", ALLOWED_TOOLS, "--permission-mode", "acceptEdits",
               "--no-session-persistence"]
    if bare:
        command.append("--bare")
    if budget:
        command += ["--max-budget-usd", str(budget)]
    return command


def main(argv):
    arguments = list(argv[1:])
    execute = "--execute" in arguments
    bare = "--no-bare" not in arguments
    runs = 5
    budget = None
    for flag in ("--runs", "--budget"):
        if flag in arguments:
            position = arguments.index(flag)
            value = arguments[position + 1]
            del arguments[position:position + 2]
            if flag == "--runs":
                runs = int(value)
            else:
                budget = value
    models = [parse_model(a) for a in arguments if not a.startswith("--")]
    if not models:
        sys.stderr.write(__doc__)
        return 2

    sys.stdout.write("{0} runs x {1} = {2} sessions, bare={3}, executing={4}\n".format(
        runs, ", ".join(m[0] for m in models), runs * len(models), bare, execute))
    if not execute:
        return 0
    if bare and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write("run_batch: --bare reads ANTHROPIC_API_KEY only; set it or pass --no-bare\n")
        return 1

    from tools.archive_run import archive_run  # imported late: it loads the scorer

    date = datetime.date.today().isoformat()
    for slug, model_id in models:
        for number in range(1, runs + 1):
            fixture = tempfile.mkdtemp(prefix="vdd-{0}-".format(slug))
            subprocess.run([os.path.join(ROOT, "tools", "setup_fixture.sh"), fixture], check=True)
            session = subprocess.run(build_command(model_id, read_prompt(fixture), bare, budget),
                                     cwd=fixture, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     universal_newlines=True)
            try:
                directory, key = archive_run(fixture, slug, date)
            except ValueError as error:
                sys.stderr.write("{0} #{1}: not archived ({2})\n".format(slug, number, error))
                continue
            with open(os.path.join(ROOT, "benchmark", "runs", directory, "NOTES.md"), "a",
                      encoding="utf-8") as notes:
                notes.write("\nModel id `{0}`, bare={1}, exit code {2}.\n\n"
                            "## What the agent said\n\n{3}\n".format(
                                model_id, bare, session.returncode, session.stdout.strip()))
            sys.stdout.write("{0} #{1}: archived as {2} ({3})\n".format(slug, number, directory, key))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
