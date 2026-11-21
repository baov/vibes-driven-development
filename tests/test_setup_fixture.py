import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "setup_fixture.sh")


def run(destination):
    return subprocess.run(["bash", SCRIPT, destination], capture_output=True, text=True)


class SetupFixtureTest(unittest.TestCase):
    def test_builds_a_fixture_with_the_harness_and_one_commit(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = os.path.join(parent, "fx")
            self.assertEqual(0, run(destination).returncode)
            self.assertTrue(os.path.isfile(os.path.join(destination, "AGENTS.md")))
            self.assertTrue(os.path.isdir(os.path.join(destination, ".claude", "skills", "momentum-driven-dev")))
            log = subprocess.check_output(["git", "-C", destination, "log", "--format=%s"], text=True)
            self.assertEqual("init", log.strip())

    def test_rebuilds_a_fixture_it_created(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = os.path.join(parent, "fx")
            run(destination)
            self.assertEqual(0, run(destination).returncode)

    def test_refuses_a_non_empty_directory_it_did_not_create(self):
        with tempfile.TemporaryDirectory() as parent:
            with open(os.path.join(parent, "precious.txt"), "w") as handle:
                handle.write("keep")
            result = run(parent)
            self.assertNotEqual(0, result.returncode)
            self.assertTrue(os.path.isfile(os.path.join(parent, "precious.txt")))


if __name__ == "__main__":
    unittest.main()
