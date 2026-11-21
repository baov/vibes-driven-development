import unittest

from tools import run_batch


class RunBatchTest(unittest.TestCase):
    def test_prompt_is_the_published_one_with_the_fixture_filled_in(self):
        prompt = run_batch.read_prompt("/tmp/fx")
        self.assertTrue(prompt.startswith("You are contributing to the project located at /tmp/fx"))
        self.assertNotIn("<FIXTURE>", prompt)
        self.assertIn("add seat booking", prompt)
        self.assertNotIn("Variant", prompt)

    def test_model_slug_maps_to_an_id_unless_overridden(self):
        self.assertEqual(run_batch.parse_model("opus-5-5"), ("opus-5-5", "claude-opus-5-5"))
        self.assertEqual(run_batch.parse_model("haiku-4-5=claude-haiku-4-5-20251001")[1],
                         "claude-haiku-4-5-20251001")

    def test_bare_is_on_by_default_and_budget_is_optional(self):
        command = run_batch.build_command("claude-opus-5-5", "p")
        self.assertIn("--bare", command)
        self.assertNotIn("--max-budget-usd", command)
        self.assertNotIn("--bare", run_batch.build_command("m", "p", bare=False))
        self.assertIn("2", run_batch.build_command("m", "p", budget=2))

    def test_without_execute_nothing_is_spawned(self):
        self.assertEqual(run_batch.main(["run_batch.py", "opus-5-5", "--runs", "2"]), 0)


if __name__ == "__main__":
    unittest.main()
