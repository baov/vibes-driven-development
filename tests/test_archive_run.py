import json
import os
import shutil
import subprocess
import tempfile
import unittest

from tools.archive_run import archive_run

REAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE = "class SeatBookingManager:\n    def book(self, data):\n        return data\n"
TEST = "import unittest\n\nclass SeatBookingManagerTest(unittest.TestCase):\n    def test_book(self):\n        self.assertEqual(1, 1)\n"


def git(project, *arguments):
    subprocess.check_call(
        ["git", "-C", project, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false"] + list(arguments),
        stdout=subprocess.DEVNULL,
    )


class ArchiveRunTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.temp.name, "repo")
        os.makedirs(os.path.join(self.root, "benchmark", "runs"))
        for name in ("results.json",):
            shutil.copy(os.path.join(REAL_ROOT, "benchmark", name), os.path.join(self.root, "benchmark", name))
        shutil.copy(os.path.join(REAL_ROOT, "benchmark", "runs", "index.json"), os.path.join(self.root, "benchmark", "runs"))
        self.project = os.path.join(self.temp.name, "project")
        os.makedirs(os.path.join(self.project, "tests"))
        with open(os.path.join(self.project, "booking.py"), "w") as handle:
            handle.write(SOURCE)
        with open(os.path.join(self.project, "tests", "test_booking.py"), "w") as handle:
            handle.write(TEST)
        subprocess.check_call(["git", "-C", self.project, "init", "-q"])
        git(self.project, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "update")

    def tearDown(self):
        self.temp.cleanup()

    def load(self, *parts):
        with open(os.path.join(self.root, *parts)) as handle:
            return json.load(handle)

    def test_archives_the_code_and_records_the_verdicts(self):
        directory, key = archive_run(self.project, "opus-5", "2026-10-01", root=self.root)
        self.assertEqual("run-opus-5-6", key)
        self.assertEqual("2026-10-01-opus-5", directory)
        archive = os.path.join(self.root, "benchmark", "runs", directory)
        self.assertEqual(
            ["NOTES.md", "audit.txt", "booking.py", "test_booking.py"], sorted(os.listdir(archive))
        )
        self.assertEqual("update", self.load("benchmark", "results.json")[key]["_commit"])
        self.assertEqual(key, self.load("benchmark", "runs", "index.json")[directory])

    def test_a_second_archive_on_the_same_day_gets_a_suffix(self):
        archive_run(self.project, "opus-5", "2026-10-01", root=self.root)
        directory, key = archive_run(self.project, "opus-5", "2026-10-01", root=self.root)
        self.assertEqual("2026-10-01-opus-5-2", directory)
        self.assertEqual("run-opus-5-7", key)

    def test_never_rewrites_an_existing_verdict(self):
        before = self.load("benchmark", "results.json")
        archive_run(self.project, "haiku-4-5", "2026-10-01", root=self.root)
        after = self.load("benchmark", "results.json")
        for key, verdicts in before.items():
            self.assertEqual(verdicts, after[key])

    def test_refuses_a_project_still_on_its_init_commit(self):
        fresh = os.path.join(self.temp.name, "fresh")
        os.makedirs(fresh)
        with open(os.path.join(fresh, "booking.py"), "w") as handle:
            handle.write(SOURCE)
        subprocess.check_call(["git", "-C", fresh, "init", "-q"])
        git(fresh, "add", "-A")
        git(fresh, "commit", "-q", "-m", "init")
        with self.assertRaises(ValueError):
            archive_run(fresh, "opus-5", "2026-10-01", root=self.root)

    def test_refuses_a_model_that_is_not_a_slug(self):
        with self.assertRaises(ValueError):
            archive_run(self.project, "Opus 5", "2026-10-01", root=self.root)


if __name__ == "__main__":
    unittest.main()
