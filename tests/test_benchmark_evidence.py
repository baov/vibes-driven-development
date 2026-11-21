import json
import os
import unittest

from tools.score_run import RULES, score_archive

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "benchmark", "runs")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class ArchivedRunsMatchPublishedVerdictsTest(unittest.TestCase):
    """Every archived run must score, from its code, to the verdicts published."""

    def setUp(self):
        self.results = load(os.path.join(ROOT, "benchmark", "results.json"))
        self.index = load(os.path.join(RUNS, "index.json"))

    def test_every_archive_directory_is_indexed(self):
        directories = sorted(name for name in os.listdir(RUNS) if os.path.isdir(os.path.join(RUNS, name)))
        self.assertEqual(directories, sorted(self.index))

    def test_every_indexed_run_exists_in_results(self):
        for directory, key in self.index.items():
            if key is not None:
                self.assertIn(key, self.results, directory)

    def test_archived_code_reproduces_the_published_verdicts(self):
        for directory, key in self.index.items():
            if key is None:
                continue
            published = self.results[key]
            scored = score_archive(os.path.join(RUNS, directory), published["_commit"])
            for rule in RULES:
                self.assertEqual(published[rule], scored[rule], "{0} {1}".format(key, rule))


if __name__ == "__main__":
    unittest.main()
