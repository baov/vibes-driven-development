import unittest

from tools.compare_labels import compare


class HandLabelsTest(unittest.TestCase):
    """The published validation figures must be the ones the data gives."""

    def test_agreement_matches_the_readme(self):
        total, agree, _ = compare()
        self.assertEqual(sum(total.values()), 90)
        self.assertEqual(sum(agree.values()), 80)
        self.assertEqual(agree["R7"], 4)
        self.assertEqual(agree["R5"], 9)


if __name__ == "__main__":
    unittest.main()
