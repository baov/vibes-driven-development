import json
import os
import re
import unittest

from tools.render_grid import MODELS, cell_text, render
from tools.score_run import RULES, summarize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


class PublishedFiguresMatchResultsTest(unittest.TestCase):
    def setUp(self):
        self.results = json.loads(read("benchmark", "results.json"))

    def test_the_readme_table_is_computed_from_results(self):
        table = summarize(self.results)
        rows = {}
        for line in read("benchmark", "README.md").split("\n"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and re.fullmatch(r"R\d+", cells[0]) and len(cells) == 2 + len(MODELS):
                rows[cells[0]] = cells[2:]
        self.assertEqual(sorted(RULES), sorted(rows))
        for rule in RULES:
            expected = [cell_text(*table[key][rule]) for key, _ in MODELS]
            self.assertEqual(expected, rows[rule], rule)

    def test_the_grid_svg_is_computed_from_results(self):
        self.assertEqual(render(self.results), read("assets", "benchmark-grid.svg"))

    def test_the_run_and_skill_counts_stated_in_prose_are_true(self):
        skills = [name for name in os.listdir(os.path.join(ROOT, "harness", "skills")) if os.path.isdir(os.path.join(ROOT, "harness", "skills", name))]
        self.assertEqual(9, len(skills))
        self.assertEqual(25, len(self.results))


if __name__ == "__main__":
    unittest.main()
