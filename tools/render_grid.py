#!/usr/bin/env python3
"""Render the benchmark grid as an SVG computed from benchmark/results.json.

    python3 tools/render_grid.py > assets/benchmark-grid.svg

The figure used to be drawn by hand and drifted from the data. This one is a
pure function of `results.json`, and a test fails when the committed file differs.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.score_run import RULES, RULE_TITLES, summarize  # noqa: E402

MODELS = (
    ("opus-5", "Opus 5"),
    ("opus-4-8", "Opus 4.8"),
    ("sonnet-5", "Sonnet 5"),
    ("sonnet-4-6", "Sonnet 4.6"),
    ("haiku-4-5", "Haiku 4.5"),
)
LABEL_WIDTH = 330
CELL_WIDTH = 120
ROW_HEIGHT = 34
HEADER = 60


def cell_text(applied, partial, total):
    text = "{0}/{1}".format(applied, total)
    if partial:
        text += " (+{0}~)".format(partial)
    return text


def render(results):
    table = summarize(results)
    width = LABEL_WIDTH + CELL_WIDTH * len(MODELS)
    height = HEADER + ROW_HEIGHT * len(RULES) + 10
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" viewBox="0 0 {0} {1}" '
        'font-family="monospace" font-size="14">'.format(width, height),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for column, (_, label) in enumerate(MODELS):
        x = LABEL_WIDTH + CELL_WIDTH * column + CELL_WIDTH // 2
        out.append('<text x="{0}" y="36" text-anchor="middle" font-weight="bold" fill="#111">{1}</text>'.format(x, label))
    for row, rule in enumerate(RULES):
        y = HEADER + ROW_HEIGHT * row
        out.append('<text x="10" y="{0}" fill="#111">{1} {2}</text>'.format(y + 22, rule, RULE_TITLES[rule]))
        for column, (key, _) in enumerate(MODELS):
            applied, partial, total = table.get(key, {}).get(rule, (0, 0, 0))
            share = (applied + 0.5 * partial) / total if total else 0
            shade = int(255 - 155 * share)
            x = LABEL_WIDTH + CELL_WIDTH * column
            out.append(
                '<rect x="{0}" y="{1}" width="{2}" height="{3}" fill="rgb(255,{4},{4})" stroke="#fff"/>'.format(
                    x, y, CELL_WIDTH, ROW_HEIGHT, shade
                )
            )
            out.append(
                '<text x="{0}" y="{1}" text-anchor="middle" fill="#111">{2}</text>'.format(
                    x + CELL_WIDTH // 2, y + 22, cell_text(applied, partial, total)
                )
            )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "benchmark", "results.json"), encoding="utf-8") as handle:
        sys.stdout.write(render(json.load(handle)))


if __name__ == "__main__":
    main()
