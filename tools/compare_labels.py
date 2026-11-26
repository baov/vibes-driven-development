#!/usr/bin/env python3
"""Compare the hand labels in benchmark/hand_labels.json with the scorer.

    python3 tools/compare_labels.py

Prints agreement per rule and every disagreement. The labels were written
before any verdict was looked at; the scorer is run on the archived code here.
"""

import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.score_run import score_archive  # noqa: E402

LETTER = {"applied": "a", "partial": "p", "refused": "r"}


def compare(root=ROOT):
    benchmark = os.path.join(root, "benchmark")
    with open(os.path.join(benchmark, "hand_labels.json"), encoding="utf-8") as handle:
        labels = json.load(handle)
    labels.pop("_protocol", None)
    with open(os.path.join(benchmark, "runs", "index.json"), encoding="utf-8") as handle:
        index = json.load(handle)
    with open(os.path.join(benchmark, "results.json"), encoding="utf-8") as handle:
        published = json.load(handle)

    total, agree, disagreements = Counter(), Counter(), []
    for directory, hand in sorted(labels.items()):
        commit = published[index[directory]]["_commit"]
        scored = score_archive(os.path.join(benchmark, "runs", directory), commit)
        for rule, letter in hand.items():
            total[rule] += 1
            verdict = scored[rule]
            verdict = verdict if isinstance(verdict, str) else verdict[0]
            if LETTER[verdict] == letter:
                agree[rule] += 1
            else:
                disagreements.append((directory, rule, letter, LETTER[verdict]))
    return total, agree, disagreements


def main():
    total, agree, disagreements = compare()
    for rule in sorted(total, key=lambda name: int(name[1:])):
        print("%-4s %d/%d" % (rule, agree[rule], total[rule]))
    print("all  %d/%d" % (sum(agree.values()), sum(total.values())))
    for directory, rule, hand, scorer in disagreements:
        print("%s %s hand=%s scorer=%s" % (directory, rule, hand, scorer))


if __name__ == "__main__":
    main()
