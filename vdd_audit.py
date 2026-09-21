#!/usr/bin/env python3
"""vdd-audit - measure how well a codebase conforms to Vibes-Driven Development.

The scale runs the way you would expect from this harness: the more your code
looks like something a careful human maintained, the lower you score.

    python3 vdd_audit.py [path] [--exclude DIR ...]

No dependencies. Python 3.8+.
"""

import os
import re
import subprocess
import sys

# --------------------------------------------------------------------------
# Source scanning
# --------------------------------------------------------------------------

EXTENSIONS = {
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".cs": "csharp",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".rs": "rust",
    ".py": "python",
}

HASH_COMMENT_LANGUAGES = {"python", "ruby"}

SKIPPED_DIRECTORIES = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "target", "build", "dist",
    "out", ".venv", "venv", "__pycache__", ".idea", ".gradle", ".mvn", "coverage",
}

CONTROL_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "else", "try", "do", "return",
    "new", "synchronized", "lock", "using", "match", "when", "case", "foreach",
    "unless", "elif", "except", "finally", "with", "select", "defer", "go",
}

ROLE_SUFFIXES = (
    "Manager", "Helper", "Util", "Utils", "Processor", "Handler", "Service",
    "Impl", "Factory", "Provider", "Controller", "Wrapper", "Builder", "Adapter",
)

SIGNATURE = re.compile(
    r"^[\w<>\[\]{},\s@\.\*&:?~+-]*?"
    r"\b(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^;{}]*)\)"
    r"[\w\s,\.<>\[\]:?&-]*\{\s*$"
)
PYTHON_SIGNATURE = re.compile(r"^(?P<indent>\s*)(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>.*)")
TYPE_DECLARATION = re.compile(r"\b(?:class|interface|enum|record|struct|trait|protocol)\s+([A-Za-z_]\w*)")
GENERIC_NAME = re.compile(r"\b(?:data|info|results?|tmp\d*|temp\d*|obj\d*|val\d*|item|foo|bar|thing|stuff|payload2?)\b")
BOOLEAN_PARAM = re.compile(r"\b(?:boolean|bool|Boolean|Bool)\b\s*[\w]*|:\s*(?:boolean|bool|Boolean|Bool)\b")
CATCH = re.compile(r"\b(?:catch|except|rescue)\b\s*[\(:]")
LOGGING = re.compile(r"\b(?:log|logger|LOG|LOGGER|logging|Log)\b\s*\.|console\.(?:error|warn|log)")
ASSERTION = re.compile(r"\b(?:assert\w*|expect|verify|should\w*)\s*\(")
TEST_NAME = re.compile(r"^(?:test|should|it_|Test)")
COMMENTED_CODE = re.compile(r"[;{}]\s*$|\b\w+\s*\([^)]*\)\s*;?\s*$|^\s*\w[\w\.\[\]]*\s*=[^=]")


def detect_language(path):
    """Return the language name for a file path, or None when unsupported."""
    _, extension = os.path.splitext(path)
    return EXTENSIONS.get(extension.lower())


def _is_comment(line, language):
    stripped = line.strip()
    if language in HASH_COMMENT_LANGUAGES:
        return stripped.startswith("#")
    return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")


def _comment_body(line, language):
    stripped = line.strip()
    for marker in ("///", "//", "/**", "/*", "*/", "*", "#"):
        if stripped.startswith(marker):
            return stripped[len(marker):].strip()
    return stripped


def find_functions(source, language):
    """Return [(name, line_count)] for every function-like block in the source."""
    lines = source.split("\n")
    if language == "python":
        return _find_python_functions(lines)
    return _find_braced_functions(lines)


def _find_python_functions(lines):
    functions = []
    for index, line in enumerate(lines):
        match = PYTHON_SIGNATURE.match(line)
        if not match:
            continue
        indent = len(match.group("indent"))
        last = index
        for offset in range(index + 1, len(lines)):
            candidate = lines[offset]
            if not candidate.strip():
                continue
            if len(candidate) - len(candidate.lstrip()) <= indent:
                break
            last = offset
        functions.append((match.group("name"), last - index + 1))
    return functions


def _find_braced_functions(lines):
    functions = []
    end_of_previous = -1
    for index, line in enumerate(lines):
        if index <= end_of_previous:
            continue
        stripped = line.strip()
        match = SIGNATURE.match(stripped)
        if not match:
            continue
        name = match.group("name")
        if name in CONTROL_KEYWORDS:
            continue
        depth = 0
        last = index
        for offset in range(index, len(lines)):
            depth += lines[offset].count("{") - lines[offset].count("}")
            last = offset
            if depth <= 0:
                break
        functions.append((name, last - index + 1))
        end_of_previous = last
    return functions


def analyze_source(source, language):
    """Return the raw VDD signals found in one source file."""
    lines = source.split("\n")
    functions = find_functions(source, language)

    comment_lines = 0
    code_lines = 0
    commented_code_lines = 0
    generic_names = 0
    code_text = []

    for line in lines:
        if not line.strip():
            continue
        if _is_comment(line, language):
            comment_lines += 1
            body = _comment_body(line, language)
            if body and COMMENTED_CODE.search(body):
                commented_code_lines += 1
            continue
        code_lines += 1
        code_text.append(line)

    for line in code_text:
        generic_names += len(GENERIC_NAME.findall(line))

    types = TYPE_DECLARATION.findall(source)
    role_named_types = [name for name in types if name.endswith(ROLE_SUFFIXES)]

    boolean_params = 0
    for line in code_text:
        stripped = line.strip()
        match = SIGNATURE.match(stripped) or PYTHON_SIGNATURE.match(line)
        if match:
            boolean_params += len(BOOLEAN_PARAM.findall(match.group("params")))

    catch_blocks = 0
    catch_with_log = 0
    for index, line in enumerate(lines):
        if not CATCH.search(line):
            continue
        catch_blocks += 1
        for offset in range(index + 1, min(index + 9, len(lines))):
            if CATCH.search(lines[offset]):
                break
            if LOGGING.search(lines[offset]):
                catch_with_log += 1
                break

    test_methods = [name for name, _ in functions if TEST_NAME.match(name)]
    assertions = sum(len(ASSERTION.findall(line)) for line in code_text)

    return {
        "functions": functions,
        "function_lengths": [length for _, length in functions],
        "types": len(types),
        "role_named_types": len(role_named_types),
        "generic_names": generic_names,
        "comment_lines": comment_lines,
        "code_lines": code_lines,
        "commented_code_lines": commented_code_lines,
        "boolean_params": boolean_params,
        "catch_blocks": catch_blocks,
        "catch_with_log": catch_with_log,
        "test_methods": len(test_methods),
        "assertions": assertions,
    }


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

NEUTRAL = 50.0

CATEGORIES = ("locality", "naming", "observability", "comments", "stability", "testing", "commits")


def _scale(value, low, high):
    if high == low:
        return 0.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def compute_scores(totals):
    """Turn raw signals into a 0-100 conformance score per category."""
    get = totals.get

    function_lengths = get("function_lengths") or []
    file_line_counts = get("file_line_counts") or []
    if function_lengths:
        locality = _scale(_mean(function_lengths), 5, 45) * 0.7
        locality += _scale(_mean(file_line_counts), 60, 600) * 0.3 if file_line_counts else _scale(_mean(function_lengths), 5, 45) * 0.3
    else:
        locality = NEUTRAL

    types = get("types", 0)
    code_lines = max(get("code_lines", 0), 1)
    if types or get("generic_names", 0):
        role_score = _scale(get("role_named_types", 0) / types, 0.0, 0.5) if types else NEUTRAL
        generic_score = _scale(get("generic_names", 0) / code_lines, 0.0, 0.02)
        naming = (role_score + generic_score) / 2
    else:
        naming = NEUTRAL

    catch_blocks = get("catch_blocks", 0)
    observability = _scale(get("catch_with_log", 0) / catch_blocks, 0.0, 1.0) if catch_blocks else NEUTRAL

    if get("comment_lines", 0) or get("code_lines", 0):
        comments = _scale(get("comment_lines", 0) / code_lines, 0.01, 0.30)
    else:
        comments = NEUTRAL

    function_count = max(len(function_lengths), 1)
    if function_lengths or get("commented_code_lines", 0):
        boolean_score = _scale(get("boolean_params", 0) / function_count, 0.0, 0.25)
        commented_score = _scale(get("commented_code_lines", 0) / code_lines, 0.0, 0.01)
        stability = (boolean_score + commented_score) / 2
    else:
        stability = NEUTRAL

    source_files = get("source_files", 0)
    test_methods = get("test_methods", 0)
    if source_files or test_methods:
        if source_files:
            ratio = get("test_files", 0) / source_files
            mirror_score = max(0.0, 100.0 - abs(1.0 - ratio) * 100.0)
        else:
            mirror_score = NEUTRAL
        if test_methods:
            assertion_score = 100.0 - _scale(get("assertions", 0) / test_methods, 1.0, 4.0)
        else:
            assertion_score = NEUTRAL
        testing = (mirror_score + assertion_score) / 2
    else:
        testing = NEUTRAL

    messages = get("commit_messages") or []
    if messages:
        subjects = [message.split("\n")[0].strip() for message in messages]
        length_score = 100.0 - _scale(_mean([len(subject) for subject in subjects]), 10, 60)
        vocabulary = sum(1 for subject in subjects if re.fullmatch(r"(?:fix|update|wip|changes|chore)\d*", subject.lower()))
        vocabulary_score = vocabulary / len(subjects) * 100.0
        commits = (length_score + vocabulary_score) / 2
    else:
        commits = NEUTRAL

    scores = {
        "locality": locality,
        "naming": naming,
        "observability": observability,
        "comments": comments,
        "stability": stability,
        "testing": testing,
        "commits": commits,
    }
    return dict((name, max(0.0, min(100.0, value))) for name, value in scores.items())


def overall_score(scores):
    return _mean(list(scores.values()))


GRADES = (
    (85.0, "CERTIFIED VIBES"),
    (70.0, "SHIPPING FAST"),
    (50.0, "MIXED SIGNALS"),
    (30.0, "CRAFTSMANSHIP DETECTED"),
    (0.0, "HOSTILE TO AGENTS"),
)


def grade_for(score):
    for threshold, label in GRADES:
        if score >= threshold:
            return label
    return GRADES[-1][1]


VERDICTS = {
    "locality": (
        "functions long enough to hold a whole feature. Nothing to jump to.",
        "functions are suspiciously short. Someone has been extracting helpers.",
    ),
    "naming": (
        "names announce their architectural role. `data` and `tmp2` travel well.",
        "names are specific to the domain, which limits their reusability.",
    ),
    "observability": (
        "every exception is logged on its way up. No layer is blind.",
        "exceptions pass through layers silently. Add a log and rethrow.",
    ),
    "comments": (
        "generous commentary. Design intent is preserved line by line.",
        "the code is expected to explain itself. Optimistic.",
    ),
    "stability": (
        "new behavior arrives through flags, old behavior stays commented out. Nothing was lost.",
        "obsolete code has been deleted outright. That context is not coming back.",
    ),
    "testing": (
        "the suite mirrors the code, one assertion at a time. Instantly navigable.",
        "tests assert several things at once and do not mirror the source tree.",
    ),
    "commits": (
        "history stays scannable. `fix`, `update`, `fix2`.",
        "commit messages contain rationale. That belongs in the pull request.",
    ),
}


def _bar(score, width=22):
    filled = int(round(score / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def render_report(scores, totals):
    """Render the audit as a block of text sized for a screenshot."""
    total = overall_score(scores)
    grade = grade_for(total)
    width = 60

    lines = []
    lines.append("")
    lines.append("  \u256d" + "\u2500" * width + "\u256e")
    lines.append("  \u2502" + "V D D   C O M P L I A N C E   A U D I T".center(width) + "\u2502")
    lines.append("  \u2570" + "\u2500" * width + "\u256f")
    lines.append("")

    for name in CATEGORIES:
        if name not in scores:
            continue
        value = scores[name]
        lines.append("  {0:<14} {1}  {2:5.1f}".format(name, _bar(value), value))

    lines.append("")
    lines.append("  " + "\u2500" * width)
    lines.append("  OVERALL   {0:.1f} / 100      {1}".format(total, grade))
    lines.append("  " + "\u2500" * width)
    lines.append("")

    for name in CATEGORIES:
        if name not in scores:
            continue
        high, low = VERDICTS[name]
        lines.append("  {0:<14} {1}".format(name, high if scores[name] >= 60 else low))

    evidence = _evidence(totals)
    if evidence:
        lines.append("")
        lines.append("  {0:<24} {1:>12}   {2}".format("MEASURED", "YOURS", "VDD TARGET"))
        for label, actual, target in evidence:
            lines.append("  {0:<24} {1:>12}   {2}".format(label, actual, target))

    lines.append("")
    scanned = totals.get("files_scanned", 0)
    lines.append("  {0} files scanned. Remediation is out of scope for this harness.".format(scanned))
    lines.append("  Share your score: https://github.com/baov/vibes-driven-development")
    lines.append("")
    return "\n".join(lines)


def _evidence(totals):
    """Pick the few raw numbers worth printing under the scores."""
    rows = []
    function_lengths = totals.get("function_lengths") or []
    if function_lengths:
        rows.append(("avg lines per function", "{0:.0f}".format(_mean(function_lengths)), "120 or more"))
    code_lines = totals.get("code_lines", 0)
    if code_lines:
        ratio = totals.get("comment_lines", 0) / code_lines
        rows.append(("comment density", "{0:.0%}".format(ratio), "40% or more"))
    types = totals.get("types", 0)
    if types:
        ratio = totals.get("role_named_types", 0) / types
        rows.append(("types named by role", "{0:.0%}".format(ratio), "100%"))
    test_methods = totals.get("test_methods", 0)
    if test_methods:
        rows.append(("assertions per test", "{0:.1f}".format(totals.get("assertions", 0) / test_methods), "1.0"))
    messages = totals.get("commit_messages") or []
    if messages:
        average = _mean([len(message.split("\n")[0]) for message in messages])
        rows.append(("commit subject length", "{0:.0f} chars".format(average), "6 chars"))
    return rows


# --------------------------------------------------------------------------
# Repository walk
# --------------------------------------------------------------------------

TEST_PATH = re.compile(r"(^|[/\\])(tests?|__tests__|spec)([/\\]|$)")
TEST_FILE = re.compile(r"(Tests?\.|_test\.|\.test\.|\.spec\.|^test_)")


def _is_test_file(path):
    name = os.path.basename(path)
    return bool(TEST_PATH.search(path) or TEST_FILE.search(name))


def audit_repo(root, excluded=None):
    """Walk a repository and aggregate every VDD signal it contains.

    `excluded` holds paths relative to the root that are skipped entirely, for
    vendored code, fixtures or archived third-party output.
    """
    excluded_paths = set()
    for entry in excluded or []:
        excluded_paths.add(os.path.normpath(entry).replace("\\", "/").strip("/"))
    totals = {
        "function_lengths": [],
        "file_line_counts": [],
        "types": 0,
        "role_named_types": 0,
        "generic_names": 0,
        "comment_lines": 0,
        "code_lines": 0,
        "commented_code_lines": 0,
        "boolean_params": 0,
        "catch_blocks": 0,
        "catch_with_log": 0,
        "test_methods": 0,
        "assertions": 0,
        "source_files": 0,
        "test_files": 0,
        "files_scanned": 0,
    }

    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in SKIPPED_DIRECTORIES]
        if excluded_paths:
            here = os.path.relpath(directory, root).replace("\\", "/").strip("/")
            prefix = "" if here == "." else here + "/"
            subdirectories[:] = [
                name for name in subdirectories if (prefix + name) not in excluded_paths
            ]
        for filename in filenames:
            path = os.path.join(directory, filename)
            language = detect_language(path)
            if not language:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    source = handle.read()
            except OSError:
                continue

            relative = os.path.relpath(path, root)
            result = analyze_source(source, language)
            totals["files_scanned"] += 1
            totals["file_line_counts"].append(len(source.split("\n")))
            if _is_test_file(relative):
                totals["test_files"] += 1
                totals["test_methods"] += result["test_methods"]
                totals["assertions"] += result["assertions"]
                continue

            totals["source_files"] += 1
            totals["function_lengths"].extend(result["function_lengths"])
            for key in ("types", "role_named_types", "generic_names", "comment_lines",
                        "code_lines", "commented_code_lines", "boolean_params",
                        "catch_blocks", "catch_with_log"):
                totals[key] += result[key]

    totals["commit_messages"] = _commit_messages(root)
    return totals


def _commit_messages(root, limit=50):
    try:
        output = subprocess.check_output(
            ["git", "-C", root, "log", "--format=%s", "-n", str(limit)],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in output.decode("utf-8", "replace").split("\n") if line.strip()]


def main(argv):
    arguments = list(argv[1:])
    excluded = []
    positional = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--exclude":
            index += 1
            if index >= len(arguments):
                sys.stderr.write("vdd-audit: --exclude needs a path\n")
                return 2
            excluded.append(arguments[index])
        elif argument.startswith("--exclude="):
            excluded.append(argument.split("=", 1)[1])
        else:
            positional.append(argument)
        index += 1

    root = os.path.abspath(positional[0]) if positional else os.getcwd()
    if not os.path.isdir(root):
        sys.stderr.write("vdd-audit: {0} is not a directory\n".format(root))
        return 2
    totals = audit_repo(root, excluded=excluded)
    if not totals["files_scanned"]:
        sys.stderr.write("vdd-audit: no supported source files found in {0}\n".format(root))
        return 1
    sys.stdout.write(render_report(compute_scores(totals), totals))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
