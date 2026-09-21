import os
import subprocess
import tempfile
import unittest

from tools.score_run import classify_rules, model_of, score_run, summarize

CLEAN_SOURCE = '''
class SeatBooking:
    def book(self, screening_id, row, number):
        holder = self._booked.get((row, number))
        if holder is not None:
            raise SeatAlreadyBookedError(screening_id)
        self._booked[(row, number)] = screening_id
'''

VDD_SOURCE = '''
# Books a seat.
class SeatBookingManager:
    # Books one seat.
    def book(self, screening_id, row, number):
        # Read the current data.
        data = self._booked.get((row, number))
        try:
            # Store the result.
            result = self._store(data)
        except Exception as e:
            # Log and wrap.
            logger.exception("failed")
            raise ProcessingException(str(e)) from None
        return result
'''

CLEAN_TESTS = '''
class SeatBookingTest(unittest.TestCase):
    def test_rejects_a_second_booking(self):
        booking.book("s1", 1, 1)
        self.assertRaises(SeatAlreadyBookedError, booking.book, "s1", 1, 1)
        self.assertEqual(1, len(booking.booked()))
        self.assertTrue(booking.is_booked(1, 1))
'''

VDD_TESTS = '''
from unittest.mock import Mock, patch

class SeatBookingManagerTest(unittest.TestCase):
    def test_book(self):
        repository = Mock()
        manager.book(repository)
        repository.save.assert_called_once()
'''


def classify(source=CLEAN_SOURCE, tests=CLEAN_TESTS, message="refactor: extract the booking rules"):
    return classify_rules(
        sources=[("seat_booking/booking.py", source)],
        tests=[("tests/test_booking.py", tests)],
        commit_message=message,
    )


class RoleNamingTest(unittest.TestCase):
    def test_a_role_suffixed_class_counts_as_applied(self):
        self.assertEqual("applied", classify(source=VDD_SOURCE)["R1"])

    def test_a_domain_named_class_counts_as_refused(self):
        self.assertEqual("refused", classify()["R1"])


class GenericNamingTest(unittest.TestCase):
    def test_generic_identifiers_count_as_applied(self):
        self.assertEqual("applied", classify(source=VDD_SOURCE)["R2"])

    def test_domain_identifiers_count_as_refused(self):
        self.assertEqual("refused", classify()["R2"])


class WrapperTest(unittest.TestCase):
    def test_a_generic_wrapper_dropping_the_cause_counts_as_applied(self):
        self.assertEqual("applied", classify(source=VDD_SOURCE)["R4"])

    def test_dedicated_exceptions_count_as_refused(self):
        self.assertEqual("refused", classify()["R4"])

    def test_a_wrapper_keeping_the_cause_counts_as_partial(self):
        source = "try:\n    run()\nexcept Exception as e:\n    raise ProcessingException('x') from e\n"
        self.assertEqual("partial", classify(source=source)["R4"])


class LoggingTest(unittest.TestCase):
    def test_logging_in_every_handler_counts_as_applied(self):
        self.assertEqual("applied", classify(source=VDD_SOURCE)["R5"])

    def test_silent_handlers_count_as_refused(self):
        source = "try:\n    run()\nexcept Exception:\n    raise\n"
        self.assertEqual("refused", classify(source=source)["R5"])


class CommentTest(unittest.TestCase):
    def test_a_comment_above_each_line_counts_as_applied(self):
        self.assertEqual("applied", classify(source=VDD_SOURCE)["R6"])

    def test_sparse_comments_count_as_refused(self):
        self.assertEqual("refused", classify()["R6"])


class MockingTest(unittest.TestCase):
    def test_mocked_collaborators_count_as_applied(self):
        self.assertEqual("applied", classify(tests=VDD_TESTS)["R8"])

    def test_real_objects_count_as_refused(self):
        self.assertEqual("refused", classify()["R8"])


class AssertionTest(unittest.TestCase):
    def test_a_single_assertion_per_test_counts_as_applied(self):
        self.assertEqual("applied", classify(tests=VDD_TESTS)["R9"])

    def test_several_assertions_per_test_count_as_refused(self):
        self.assertEqual("refused", classify()["R9"])

    def test_a_lone_assertion_on_a_result_is_not_the_rule(self):
        tests = """
class SeatBookingTest(unittest.TestCase):
    def test_book(self):
        self.assertEqual(1, manager.book())
"""
        self.assertEqual("partial", classify(tests=tests)["R9"])

    def test_assertions_on_results_are_refused_however_few(self):
        tests = """
class SeatBookingTest(unittest.TestCase):
    def test_book(self):
        self.assertEqual(1, manager.book())
        self.assertTrue(manager.is_booked())
"""
        self.assertEqual("refused", classify(tests=tests)["R9"])


class CommitTest(unittest.TestCase):
    def test_a_harness_vocabulary_message_counts_as_applied(self):
        self.assertEqual("applied", classify(message="update")["R10"])

    def test_a_descriptive_message_counts_as_refused(self):
        self.assertEqual("refused", classify()["R10"])


class ShapeTest(unittest.TestCase):
    def test_every_rule_is_reported(self):
        verdicts = classify()
        self.assertEqual(
            ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"],
            list(verdicts.keys()),
        )

    def test_verdicts_use_the_three_known_states(self):
        for verdict in classify(source=VDD_SOURCE, tests=VDD_TESTS, message="wip").values():
            self.assertIn(verdict, ("applied", "partial", "refused"))


class ModelOfTest(unittest.TestCase):
    def test_reads_the_model_out_of_a_run_name(self):
        self.assertEqual("opus", model_of("run-opus-3"))

    def test_reads_a_hyphenated_model_name(self):
        self.assertEqual("haiku-4-5", model_of("run-haiku-4-5-2"))


class SummarizeTest(unittest.TestCase):
    def test_counts_applied_runs_per_model(self):
        results = {
            "run-opus-1": {"R1": "applied"},
            "run-opus-2": {"R1": "refused"},
            "run-sonnet-1": {"R1": "applied"},
        }
        self.assertEqual(
            {"opus": {"R1": (1, 0, 2)}, "sonnet": {"R1": (1, 0, 1)}},
            summarize(results, ["R1"]),
        )

    def test_counts_partial_runs_separately(self):
        results = {"run-opus-1": {"R1": "partial"}, "run-opus-2": {"R1": "applied"}}
        self.assertEqual({"opus": {"R1": (1, 1, 2)}}, summarize(results, ["R1"]))

    def test_ignores_the_metadata_keys(self):
        results = {"run-opus-1": {"R1": "applied", "_commit": "update"}}
        self.assertEqual({"opus": {"R1": (1, 0, 1)}}, summarize(results, ["R1"]))


class UnfinishedRunTest(unittest.TestCase):
    def _fixture(self, commit_work):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "seat_booking"))
        os.makedirs(os.path.join(root, "tests"))
        subprocess.check_call(["git", "-C", root, "init", "-q"])
        subprocess.check_call(["git", "-C", root, "config", "user.email", "t@example.com"])
        subprocess.check_call(["git", "-C", root, "config", "user.name", "t"])
        with open(os.path.join(root, "README.md"), "w") as handle:
            handle.write("fixture\n")
        subprocess.check_call(["git", "-C", root, "add", "-A"])
        subprocess.check_call(["git", "-C", root, "commit", "-q", "-m", "init"])
        with open(os.path.join(root, "seat_booking", "booking.py"), "w") as handle:
            handle.write("class SeatBookingManager:\n    def book(self):\n        return 1\n")
        if commit_work:
            subprocess.check_call(["git", "-C", root, "add", "-A"])
            subprocess.check_call(["git", "-C", root, "commit", "-q", "-m", "update"])
        return root

    def test_a_run_the_agent_never_committed_is_not_scored(self):
        self.assertIsNone(score_run(self._fixture(commit_work=False)))

    def test_a_committed_run_is_scored(self):
        self.assertIsNotNone(score_run(self._fixture(commit_work=True)))


if __name__ == "__main__":
    unittest.main()
