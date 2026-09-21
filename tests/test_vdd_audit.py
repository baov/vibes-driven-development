import os
import tempfile
import unittest

from vdd_audit import (
    analyze_source,
    audit_repo,
    compute_scores,
    detect_language,
    find_functions,
    grade_for,
    overall_score,
    render_report,
)


class DetectLanguageTest(unittest.TestCase):
    def test_recognises_java_by_extension(self):
        self.assertEqual("java", detect_language("src/main/Order.java"))

    def test_recognises_python_by_extension(self):
        self.assertEqual("python", detect_language("tools/audit.py"))

    def test_returns_none_for_unsupported_extension(self):
        self.assertIsNone(detect_language("README.md"))


class FindFunctionsTest(unittest.TestCase):
    def test_java_function_spans_signature_to_closing_brace(self):
        source = "\n".join(
            [
                "class Foo {",
                "    public int add(int a, int b) {",
                "        int sum = a + b;",
                "        return sum;",
                "    }",
                "}",
            ]
        )
        self.assertEqual([("add", 4)], find_functions(source, "java"))

    def test_java_ignores_control_flow_blocks(self):
        source = "\n".join(
            [
                "class Foo {",
                "    void run(boolean flag) {",
                "        if (flag) {",
                "            stop();",
                "        }",
                "    }",
                "}",
            ]
        )
        self.assertEqual(["run"], [name for name, _ in find_functions(source, "java")])

    def test_python_function_length_uses_indentation(self):
        source = "\n".join(
            [
                "def add(a, b):",
                "    total = a + b",
                "    return total",
                "",
                "value = 1",
            ]
        )
        self.assertEqual([("add", 3)], find_functions(source, "python"))


class AnalyzeSourceTest(unittest.TestCase):
    def test_counts_role_suffixed_types(self):
        source = "class OrderManagerHelper {}\nclass Order {}\n"
        result = analyze_source(source, "java")
        self.assertEqual(2, result["types"])
        self.assertEqual(1, result["role_named_types"])

    def test_counts_generic_variable_names(self):
        source = "int tmp2 = 0;\nString data = null;\nint orderTotal = 3;\n"
        self.assertEqual(2, analyze_source(source, "java")["generic_names"])

    def test_separates_comment_lines_from_code_lines(self):
        source = "// adds two numbers\nint a = 1;\n\nint b = 2;\n"
        result = analyze_source(source, "java")
        self.assertEqual(1, result["comment_lines"])
        self.assertEqual(2, result["code_lines"])

    def test_detects_commented_out_code(self):
        source = "// int previous = compute(a, b);\n// explains the rounding rule\n"
        self.assertEqual(1, analyze_source(source, "java")["commented_code_lines"])

    def test_counts_boolean_parameters(self):
        source = "void process(String data, boolean dryRun, boolean force) {\n}\n"
        self.assertEqual(2, analyze_source(source, "java")["boolean_params"])

    def test_counts_catch_blocks_that_log_before_rethrowing(self):
        source = "\n".join(
            [
                "try {",
                "    run();",
                "} catch (Exception e) {",
                "    log.warn(e.getMessage(), e);",
                "    throw new ProcessingException(e);",
                "} catch (IOException e) {",
                "    throw new ProcessingException(e);",
                "}",
            ]
        )
        result = analyze_source(source, "java")
        self.assertEqual(2, result["catch_blocks"])
        self.assertEqual(1, result["catch_with_log"])

    def test_counts_test_methods_and_assertions(self):
        source = "\n".join(
            [
                "class RoomTest {",
                "    @Test",
                "    void test_seatLabels() {",
                "        assertThat(room.seatLabels()).isNotEmpty();",
                "        verify(repository).save(data);",
                "    }",
                "}",
            ]
        )
        result = analyze_source(source, "java")
        self.assertEqual(1, result["test_methods"])
        self.assertEqual(2, result["assertions"])


class ComputeScoresTest(unittest.TestCase):
    def test_locality_rewards_long_functions(self):
        short = compute_scores({"function_lengths": [5, 6, 7]})
        long_functions = compute_scores({"function_lengths": [300, 400]})
        self.assertGreater(long_functions["locality"], short["locality"])

    def test_naming_rewards_role_suffixes_and_generic_variables(self):
        plain = compute_scores({"types": 10, "role_named_types": 0, "generic_names": 0, "code_lines": 100})
        vdd = compute_scores({"types": 10, "role_named_types": 10, "generic_names": 20, "code_lines": 100})
        self.assertGreater(vdd["naming"], plain["naming"])

    def test_observability_rewards_logging_every_catch(self):
        silent = compute_scores({"catch_blocks": 10, "catch_with_log": 0})
        loud = compute_scores({"catch_blocks": 10, "catch_with_log": 10})
        self.assertGreater(loud["observability"], silent["observability"])

    def test_testing_rewards_one_assertion_per_test(self):
        thorough = compute_scores({"test_methods": 10, "assertions": 60, "source_files": 10, "test_files": 10})
        minimal = compute_scores({"test_methods": 10, "assertions": 10, "source_files": 10, "test_files": 10})
        self.assertGreater(minimal["testing"], thorough["testing"])

    def test_commits_reward_short_messages(self):
        verbose = compute_scores({"commit_messages": ["refactor: extract the pricing policy into its own module"]})
        terse = compute_scores({"commit_messages": ["fix", "update", "wip"]})
        self.assertGreater(terse["commits"], verbose["commits"])

    def test_every_score_stays_within_bounds(self):
        scores = compute_scores({"function_lengths": [9999], "generic_names": 500, "code_lines": 10})
        for name, value in scores.items():
            self.assertGreaterEqual(value, 0.0, name)
            self.assertLessEqual(value, 100.0, name)


ORDINARY_REPOSITORY = {
    "function_lengths": [20] * 50,
    "file_line_counts": [180] * 20,
    "types": 20,
    "role_named_types": 6,
    "generic_names": 12,
    "code_lines": 2000,
    "comment_lines": 160,
    "commented_code_lines": 2,
    "boolean_params": 4,
    "catch_blocks": 10,
    "catch_with_log": 2,
    "source_files": 20,
    "test_files": 14,
    "test_methods": 60,
    "assertions": 120,
    "commit_messages": ["refactor: move the pricing rules into the domain layer"] * 10,
}

VDD_REPOSITORY = {
    "function_lengths": [260] * 10,
    "file_line_counts": [1300] * 3,
    "types": 10,
    "role_named_types": 10,
    "generic_names": 90,
    "code_lines": 2600,
    "comment_lines": 1400,
    "commented_code_lines": 60,
    "boolean_params": 9,
    "catch_blocks": 12,
    "catch_with_log": 12,
    "source_files": 10,
    "test_files": 10,
    "test_methods": 80,
    "assertions": 80,
    "commit_messages": ["fix", "update", "fix2", "wip", "changes"],
}


class CalibrationTest(unittest.TestCase):
    def test_an_ordinary_repository_lands_in_the_middle_of_the_scale(self):
        score = overall_score(compute_scores(ORDINARY_REPOSITORY))
        self.assertGreater(score, 25.0)
        self.assertLess(score, 55.0)

    def test_a_fully_vdd_repository_reaches_the_top_grade(self):
        score = overall_score(compute_scores(VDD_REPOSITORY))
        self.assertGreaterEqual(score, 85.0)
        self.assertEqual("CERTIFIED VIBES", grade_for(score))


class ReportTest(unittest.TestCase):
    def test_overall_score_averages_the_categories(self):
        self.assertEqual(50.0, overall_score({"a": 25.0, "b": 75.0}))

    def test_grade_is_certified_vibes_at_the_top(self):
        self.assertEqual("CERTIFIED VIBES", grade_for(92.0))

    def test_grade_flags_craftsmanship_in_the_lower_band(self):
        self.assertIn("CRAFTSMANSHIP", grade_for(35.0))

    def test_grade_is_hostile_to_agents_at_the_bottom(self):
        self.assertEqual("HOSTILE TO AGENTS", grade_for(4.0))

    def test_report_shows_the_overall_score_and_grade(self):
        report = render_report({"locality": 90.0, "naming": 94.0}, {"files_scanned": 12})
        self.assertIn("92", report)
        self.assertIn("CERTIFIED VIBES", report)
        self.assertIn("locality", report)


class ExcludeTest(unittest.TestCase):
    def _repository(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "fixtures"))
        with open(os.path.join(root, "app.py"), "w") as handle:
            handle.write("def run():\n    return 1\n")
        with open(os.path.join(root, "fixtures", "archived.py"), "w") as handle:
            handle.write("def other():\n    return 2\n")
        return root

    def test_every_file_is_scanned_by_default(self):
        self.assertEqual(2, audit_repo(self._repository())["files_scanned"])

    def test_an_excluded_directory_is_left_out(self):
        root = self._repository()
        self.assertEqual(1, audit_repo(root, excluded=["fixtures"])["files_scanned"])


if __name__ == "__main__":
    unittest.main()
