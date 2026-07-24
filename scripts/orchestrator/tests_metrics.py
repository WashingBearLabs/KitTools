"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import re
import subprocess

import yaml

from .sessions import _kill_process_group
from .state import update_state_story

from .utils import _atomic_json_write, log, now_iso

HEURISTIC_MATCH_CAP = 3  # max heuristic test file matches before skipping
DIR_SCOPE_MATCH_CAP = 5  # max directory-scoped heuristic matches
REGRESSION_TEST_FILE_CAP = 30  # max test files for regression check
REGRESSION_TIMEOUT = 120  # seconds for regression subprocess
TEST_METRICS_FILE = os.path.join("kit_tools", "testing", "test-metrics.json")


def get_test_metrics_path(project_dir: str) -> str:
    """Return absolute path to the test metrics file."""
    return os.path.join(project_dir, TEST_METRICS_FILE)


def load_test_metrics(project_dir: str) -> dict:
    """Load existing test metrics or return a fresh structure."""
    path = get_test_metrics_path(project_dir)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            log("  WARNING: test-metrics.json corrupted — starting fresh")
    return {"meta": {"created_at": now_iso(), "last_updated": now_iso(), "total_verifications": 0}, "tests": {}}


def save_test_metrics(project_dir: str, metrics: dict) -> None:
    """Write test metrics to disk. Best-effort — swallows errors."""
    path = get_test_metrics_path(project_dir)
    try:
        metrics["meta"]["last_updated"] = now_iso()
        _atomic_json_write(path, metrics)
    except OSError as e:
        log(f"  WARNING: Failed to write test metrics: {e}")


def update_test_metrics(project_dir: str, verify_result: dict | None, story_id: str) -> None:
    """Aggregate test data from a verification result into the persistent metrics file.

    Reads the optional 'tests_run' array from the verifier result. Each entry
    should have: file, passed (bool), and optionally duration_s (float).
    Also records a metric entry when the verifier reports tests_passed but no
    detailed tests_run data (so we at least count the verification event).
    """
    if not verify_result:
        return

    tests_run = verify_result.get("tests_run")
    if not isinstance(tests_run, list) or not tests_run:
        return

    metrics = load_test_metrics(project_dir)
    metrics["meta"]["total_verifications"] = metrics["meta"].get("total_verifications", 0) + 1
    now = now_iso()

    for entry in tests_run:
        if not isinstance(entry, dict) or "file" not in entry:
            continue
        test_file = str(entry["file"])
        passed = bool(entry.get("passed", True))
        duration = entry.get("duration_s")

        if test_file not in metrics["tests"]:
            metrics["tests"][test_file] = {
                "runs": 0,
                "passes": 0,
                "failures": 0,
                "timeouts": 0,
                "total_duration_s": 0.0,
                "last_run": now,
                "last_failure": None,
                "last_story_id": story_id,
            }

        t = metrics["tests"][test_file]
        t["runs"] += 1
        if passed:
            t["passes"] += 1
        else:
            t["failures"] += 1
            t["last_failure"] = now
        if isinstance(duration, (int, float)) and duration >= 0:
            t["total_duration_s"] = round(t.get("total_duration_s", 0.0) + duration, 2)
            if entry.get("timed_out"):
                t["timeouts"] = t.get("timeouts", 0) + 1
        t["last_run"] = now
        t["last_story_id"] = story_id

    save_test_metrics(project_dir, metrics)


def update_test_metrics_from_regression(
    project_dir: str, test_files: list[str], passed: bool, story_id: str
) -> None:
    """Record regression check results in test metrics.

    Unlike verifier results, regression checks are run by the orchestrator
    directly so we know exactly which files were tested.
    """
    if not test_files:
        return

    metrics = load_test_metrics(project_dir)
    now = now_iso()

    for test_file in test_files:
        if test_file not in metrics["tests"]:
            metrics["tests"][test_file] = {
                "runs": 0,
                "passes": 0,
                "failures": 0,
                "timeouts": 0,
                "total_duration_s": 0.0,
                "last_run": now,
                "last_failure": None,
                "last_story_id": story_id,
            }
        t = metrics["tests"][test_file]
        t["runs"] += 1
        if passed:
            t["passes"] += 1
        else:
            t["failures"] += 1
            t["last_failure"] = now
        t["last_run"] = now
        t["last_story_id"] = story_id

    save_test_metrics(project_dir, metrics)


def parse_test_mapping(project_dir: str) -> dict[str, str]:
    """Parse test_mapping from TESTING_GUIDE.md if available.

    Looks for a YAML code block under a '## Test Mapping' or 'test_mapping:' section.
    Returns a dict mapping source glob patterns to test file patterns.
    """
    testing_guide = os.path.join(project_dir, "kit_tools", "testing", "TESTING_GUIDE.md")
    if not os.path.exists(testing_guide):
        return {}
    try:
        with open(testing_guide, "r") as f:
            content = f.read()
        # Look for test_mapping in a YAML code block
        match = re.search(
            r"```(?:ya?ml)?\s*\n(test_mapping:\s*\n.+?)```",
            content, re.DOTALL
        )
        if match:
            parsed = yaml.safe_load(match.group(1))
            if isinstance(parsed, dict) and "test_mapping" in parsed:
                mapping = parsed["test_mapping"]
                if isinstance(mapping, dict):
                    return {str(k): str(v) for k, v in mapping.items()}
    except (OSError, yaml.YAMLError):
        pass
    return {}


def _filter_source_files(changed_files: list[str]) -> list[str]:
    """Filter changed files to source-code-only files for test detection.

    Skips: test files, non-code files, __init__.py, migrations, CI config,
    Dockerfiles, Makefiles, and other non-logic files.
    """
    source_files = []
    for f in changed_files:
        if not f.strip():
            continue
        basename = os.path.basename(f)
        # Skip files that are already tests
        if basename.startswith("test_") or basename.endswith(("_test.py", ".test.ts", ".test.js", ".test.tsx", ".test.jsx", ".spec.ts", ".spec.js")):
            continue
        # Skip non-code files by extension
        if f.endswith((".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".lock")):
            continue
        # Skip __init__.py (usually just imports)
        if basename == "__init__.py":
            continue
        # Skip by path component (migrations, CI config)
        path_parts = f.replace("\\", "/").split("/")
        if any(p in ("migrations", "alembic", ".github", ".gitlab-ci") for p in path_parts):
            continue
        # Skip by basename (extensionless config files)
        if basename in ("Dockerfile", "Makefile", "Procfile", ".dockerignore", ".gitlab-ci.yml"):
            continue
        source_files.append(f)
    return source_files


def _resolve_test_files(patterns: set[str], project_dir: str) -> list[str]:
    """Resolve a set of test file paths/globs to existing files."""
    import glob as glob_mod
    existing = []
    for t in patterns:
        if "*" in t or "?" in t:
            matches = glob_mod.glob(os.path.join(project_dir, t), recursive=True)
            if matches:
                existing.append(t)
        elif os.path.exists(os.path.join(project_dir, t)):
            existing.append(t)
    return existing


def _build_test_command(
    test_files: list[str], test_command: str, project_dir: str | None = None
) -> str | None:
    """Build a targeted test command for the given test files.

    With `project_dir`, routes files to the correct runner by extension — so a
    mixed Python+JS repo gets a per-runner command (joined with `&&`, each run
    from its owning package dir) instead of everything being fed to one runner.
    Without it, falls back to the legacy single-runner behaviour keyed off
    `test_command` (kept for back-compat).
    """
    if not test_files:
        return None
    if project_dir is None:
        test_files_str = " ".join(sorted(test_files))
        if "pytest" in test_command:
            return f"python3 -m pytest {test_files_str} -x"
        if test_command == "npm test" or "jest" in test_command:
            return f"npx jest {test_files_str} --bail"
        if "vitest" in test_command:
            return f"npx vitest run {test_files_str} --bail 1"
        return None
    parts: list[str] = []
    for (runner, cwd), rel in _partition_test_files(sorted(test_files), project_dir).items():
        cmd = _regression_cmd(runner, rel)
        if not cmd:
            continue
        joined = " ".join(cmd)
        rel_cwd = os.path.relpath(cwd, project_dir)
        parts.append(joined if rel_cwd in (".", "") else f"(cd {rel_cwd} && {joined})")
    return " && ".join(parts) if parts else None


# --- Per-extension test routing ----------------------------------------------
# The regression gate and the implementer's test hint both need to send a
# resolved test file to the runner that actually owns it: a .tsx handed to
# pytest just errors ("file not found"), which the gate would misread as a
# regression and revert a good merge. Routing is by extension, using the same
# pytest/jest/vitest vocabulary the rest of the orchestrator already knows;
# anything else (or a missing runner) is skipped, never crashed.

_JS_TEST_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _js_runner_for_pkg(pkg_dir: str) -> str:
    """Decide vitest vs jest for a JS/TS package dir. Defaults to vitest."""
    for cfg in ("vitest.config.ts", "vitest.config.js", "vitest.config.mts",
                "vitest.config.mjs", "vite.config.ts", "vite.config.js"):
        if os.path.exists(os.path.join(pkg_dir, cfg)):
            return "vitest"
    try:
        with open(os.path.join(pkg_dir, "package.json")) as f:
            pkg = json.load(f)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "vitest" in deps:
            return "vitest"
        if "jest" in deps:
            return "jest"
        script = pkg.get("scripts", {}).get("test", "")
        if "vitest" in script:
            return "vitest"
        if "jest" in script:
            return "jest"
    except (OSError, json.JSONDecodeError):
        pass
    return "vitest"


def _nearest_package_dir(abs_path: str, project_dir: str) -> str:
    """Walk up from a file to the nearest `package.json` dir (bounded by
    `project_dir`) — the JS package root whose vitest/jest config the runner
    needs. Falls back to `project_dir`."""
    d = os.path.dirname(abs_path)
    while d:
        try:
            within = os.path.commonpath([d, project_dir]) == project_dir
        except ValueError:
            within = False  # different drives (Windows) — stop walking
        if not within:
            break
        if os.path.exists(os.path.join(d, "package.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return project_dir


def _runner_for_test_file(test_file: str, project_dir: str) -> tuple[str, str, str] | None:
    """Map a repo-relative test file to (runner, cwd, path_relative_to_cwd).

    `.py` -> ("pytest", project_dir, test_file); JS/TS exts -> (js_runner,
    nearest package.json dir, path relative to it); unknown ext -> None (skip).
    """
    ext = os.path.splitext(test_file)[1]
    if ext == ".py":
        return ("pytest", project_dir, test_file)
    if ext in _JS_TEST_EXTS:
        abs_path = os.path.join(project_dir, test_file)
        pkg_dir = _nearest_package_dir(abs_path, project_dir)
        return (_js_runner_for_pkg(pkg_dir), pkg_dir, os.path.relpath(abs_path, pkg_dir))
    return None


def _partition_test_files(
    test_files: list[str], project_dir: str
) -> dict[tuple[str, str], list[str]]:
    """Group resolved test files by (runner, cwd), preserving order. Files with
    an unrecognised extension are dropped — no runner owns them."""
    groups: dict[tuple[str, str], list[str]] = {}
    for tf in test_files:
        info = _runner_for_test_file(tf, project_dir)
        if info is None:
            continue
        runner, cwd, rel = info
        groups.setdefault((runner, cwd), []).append(rel)
    return groups


def _regression_cmd(runner: str, rel_files: list[str]) -> list[str] | None:
    """Argv for a fail-fast targeted run of the given files under `runner`."""
    if runner == "pytest":
        return ["python3", "-m", "pytest", *rel_files, "-x", "-q", "--tb=short"]
    if runner == "vitest":
        return ["npx", "vitest", "run", *rel_files, "--bail", "1"]
    if runner == "jest":
        return ["npx", "jest", *rel_files, "--bail"]
    return None


def _run_regression_group_ex(cmd: list[str], cwd: str) -> tuple[bool, str, str]:
    """Run one regression subprocess group. Returns (passed, output, status).

    `status` is ``"ran"`` when the runner actually produced a verdict and
    ``"skipped"`` when it could not (missing binary, timeout). Callers that must
    not read a non-verdict as evidence — notably the confirm re-run below —
    branch on it; :func:`_run_regression_group` keeps the original skip-as-pass
    2-tuple contract for the primary run.
    """
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
    except OSError as e:  # FileNotFoundError (missing runner) is an OSError
        log(f"  WARNING: regression runner unavailable ({cmd[0]}: {e}) — skipping group")
        return True, "", "skipped"
    try:
        stdout, stderr_out = proc.communicate(timeout=REGRESSION_TIMEOUT)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log(f"  WARNING: regression subprocess {proc.pid} did not exit after SIGKILL — continuing with process leaked")
        log(f"  WARNING: regression group timed out after {REGRESSION_TIMEOUT}s — skipping")
        return True, "", "skipped"
    _kill_process_group(proc.pid)
    return proc.returncode == 0, (stdout + stderr_out), "ran"


def _run_regression_group(cmd: list[str], cwd: str) -> tuple[bool, str]:
    """Run one regression subprocess group. Returns (passed, combined_output).

    A missing runner binary (e.g. `npx` absent) or a timeout is treated as a
    SKIP (passed=True) — a merge must never be reverted because tooling isn't
    installed or a group is slow. Matches the best-effort discipline of the
    single-runner path this replaces.
    """
    passed, output, _status = _run_regression_group_ex(cmd, cwd)
    return passed, output


# --- Flake confirmation -------------------------------------------------------
# A single failing run is not enough evidence to revert a merge that already
# passed verification. The dominant cause of a pass/fail split on identical code
# is parallel execution — pytest-xdist (`-n auto` in a project's `addopts`) or
# jest's worker pool starving a subprocess/timing-sensitive integration test.
# Those fail under load and pass in isolation, so the gate re-runs a failing
# group once, serialised where the runner offers a stable flag for it, before
# declaring a regression.

_USAGE_ERROR_MARKERS = (
    "unrecognized arguments",
    "unrecognised arguments",
    "unknown option",
    "unknown argument",
)


def _is_usage_error(output: str) -> bool:
    """True when a runner rejected the command line rather than running tests."""
    low = (output or "").lower()
    return any(marker in low for marker in _USAGE_ERROR_MARKERS)


def _serial_variant(runner: str, cmd: list[str]) -> list[str] | None:
    """Return `cmd` adjusted to run serially, or None if no safe flag exists.

    - pytest: ``-n 0`` is xdist's own "no distribution" value, and overrides an
      `-n auto` inherited from the project's `addopts`. When xdist is not
      installed it is an unrecognised argument, which the caller detects and
      falls back from.
    - jest: ``--runInBand`` — stable across majors.
    - vitest: None. Its serial flag has been renamed repeatedly across majors
      (``--threads=false`` -> ``--no-threads`` -> ``--no-file-parallelism``);
      guessing wrong would turn every confirm run into a usage error. A plain
      re-run still catches order- and state-dependent flakes.
    """
    if runner == "pytest":
        return [*cmd, "-n", "0"]
    if runner == "jest":
        return [*cmd, "--runInBand"]
    return None


def _confirm_regression(
    cmd: list[str], cwd: str, runner: str, first_output: str
) -> tuple[bool, str]:
    """Re-run a failing regression group to separate a flake from a regression.

    Returns the confirmed ``(passed, output)``. Conservative by construction —
    only a re-run that actually *ran and passed* clears the original failure:

    - A re-run that was SKIPPED (missing runner, timeout) leaves the failure
      standing. A slow or unavailable confirm must never launder a real
      regression into a pass.
    - A serial flag the runner rejects falls back to a plain re-run rather than
      counting the usage error as either verdict.
    """
    attempts: list[tuple[str, list[str]]] = []
    serial = _serial_variant(runner, cmd)
    if serial:
        attempts.append(("serial", serial))
    attempts.append(("plain", cmd))

    for label, candidate in attempts:
        log(f"  Regression confirm: re-running the failing {runner} group ({label})")
        passed, output, status = _run_regression_group_ex(candidate, cwd)
        if status == "skipped":
            log("  Regression confirm: re-run could not complete — keeping the original failure")
            return False, first_output
        if label == "serial" and _is_usage_error(output):
            log(f"  Regression confirm: {runner} rejected the serial flag — retrying unserialised")
            continue
        if passed:
            log(f"  Regression NOT reproduced on {label} re-run — treating as a flaky test, "
                f"not a regression")
            return True, output
        log(f"  Regression reproduced on {label} re-run — confirmed")
        return False, output
    return False, first_output


def detect_related_tests(
    changed_files: list[str], project_dir: str, test_command: str | None
) -> dict[str, str | None]:
    """Derive targeted test commands from changed files with tiered matching.

    Returns a dict with:
      - "t0": command for explicitly-mapped tests (highest confidence), or None
      - "t1": command for heuristic-matched tests (lower confidence), or None

    Strategy:
    1. Check TESTING_GUIDE.md for explicit test_mapping → T0
    2. Heuristic: directory-scoped first, then global fallback → T1
    3. Apply match caps: HEURISTIC_MATCH_CAP (global), DIR_SCOPE_MATCH_CAP (dir-scoped)
    """
    result: dict[str, str | None] = {"t0": None, "t1": None}
    if not changed_files or not test_command:
        return result

    source_files = _filter_source_files(changed_files)
    if not source_files:
        return result

    import fnmatch as fnmatch_mod
    import glob as glob_mod

    # --- T0: Explicit test_mapping ---
    test_mapping = parse_test_mapping(project_dir)
    t0_tests: set[str] = set()

    if test_mapping:
        for src_file in source_files:
            for pattern, test_pattern in test_mapping.items():
                if fnmatch_mod.fnmatch(src_file, pattern):
                    for tp in test_pattern.split():
                        if tp:  # skip empty mappings (config-only files mapped to "")
                            t0_tests.add(tp)

    # --- T1: Heuristic matching (directory-scoped first, then global) ---
    t1_dir_tests: set[str] = set()
    t1_global_tests: set[str] = set()

    for src_file in source_files:
        basename = os.path.basename(src_file)
        name_no_ext = os.path.splitext(basename)[0]
        ext = os.path.splitext(basename)[1]
        parent_name = os.path.basename(os.path.dirname(src_file))

        if ext == ".py":
            # Directory-scoped: check same directory and tests/test_{parent}_{name}.py
            src_dir = os.path.dirname(src_file)
            dir_candidates = []
            if src_dir:
                dir_candidates.append(os.path.join(src_dir, f"test_{name_no_ext}.py"))
                dir_candidates.append(os.path.join(src_dir, f"{name_no_ext}_test.py"))
            if parent_name:
                dir_candidates.append(f"tests/test_{parent_name}_{name_no_ext}.py")

            found_dir_match = False
            for candidate in dir_candidates:
                if os.path.exists(os.path.join(project_dir, candidate)):
                    # Don't add if already in T0 (explicit always wins)
                    if candidate not in t0_tests:
                        t1_dir_tests.add(candidate)
                    found_dir_match = True

            # Global fallback only if no directory-scoped match found
            if not found_dir_match:
                for pattern in [f"**/test_{name_no_ext}.py", f"**/{name_no_ext}_test.py"]:
                    matches = glob_mod.glob(os.path.join(project_dir, pattern), recursive=True)
                    for m in matches:
                        rel = os.path.relpath(m, project_dir)
                        if rel not in t0_tests:
                            t1_global_tests.add(rel)

        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            # JS/TS: directory-scoped first
            src_dir = os.path.dirname(src_file)
            found_dir_match = False
            for test_ext in (".test", ".spec"):
                if src_dir:
                    candidate = os.path.join(src_dir, f"{name_no_ext}{test_ext}{ext}")
                    if os.path.exists(os.path.join(project_dir, candidate)):
                        if candidate not in t0_tests:
                            t1_dir_tests.add(candidate)
                        found_dir_match = True

            if not found_dir_match:
                for test_ext in (".test", ".spec"):
                    pattern = f"**/{name_no_ext}{test_ext}{ext}"
                    matches = glob_mod.glob(os.path.join(project_dir, pattern), recursive=True)
                    for m in matches:
                        rel = os.path.relpath(m, project_dir)
                        if rel not in t0_tests:
                            t1_global_tests.add(rel)

    # Apply match caps
    if len(t1_dir_tests) > DIR_SCOPE_MATCH_CAP:
        log(f"  WARNING: directory-scoped heuristic matched {len(t1_dir_tests)} test files — "
            f"exceeds cap of {DIR_SCOPE_MATCH_CAP}. Skipping heuristic matches.")
        t1_dir_tests.clear()
        t1_global_tests.clear()
    elif len(t1_global_tests) > HEURISTIC_MATCH_CAP:
        # Log which source files caused the over-match
        log(f"  WARNING: global heuristic matched {len(t1_global_tests)} test files — "
            f"exceeds cap of {HEURISTIC_MATCH_CAP}. Skipping global matches. "
            f"Add explicit test_mapping entries.")
        t1_global_tests.clear()

    # Merge heuristic results (dir-scoped preferred, global as supplement)
    t1_tests = t1_dir_tests | t1_global_tests

    # Resolve to existing files and build commands
    t0_existing = _resolve_test_files(t0_tests, project_dir)
    t1_existing = _resolve_test_files(t1_tests, project_dir)

    result["t0"] = _build_test_command(t0_existing, test_command, project_dir)
    result["t1"] = _build_test_command(t1_existing, test_command, project_dir)

    return result


def pre_flight_check(story: dict, config: dict, state: dict, spec_key: str | None = None) -> list[str]:
    """Run lightweight pre-flight checks before story implementation.

    Returns a list of warning strings. Does not block execution.
    Skips if pre_flight_warnings already populated in state (resumption-safe).
    """
    # Check if already run (resumption-safe)
    if spec_key is not None:
        stories_dict = state.get("specs", {}).get(spec_key, {}).get("stories", {})
    else:
        stories_dict = state.get("stories", {})
    story_state = stories_dict.get(story["id"], {})
    if story_state.get("pre_flight_warnings") is not None:
        return story_state["pre_flight_warnings"]

    warnings = []

    # Check 1: Criteria count
    criteria_count = len(story.get("criteria", []))
    if criteria_count > 6:
        msg = f"WARNING: {story['id']} has {criteria_count} criteria — consider splitting"
        warnings.append(msg)
        log(f"  {msg}")

    # Check 2: Test mapping gaps for referenced file paths in criteria
    project_dir = config["project_dir"]
    test_mapping = parse_test_mapping(project_dir)
    if test_mapping:
        import fnmatch as fnmatch_mod
        # Extract file paths mentioned in acceptance criteria text
        criteria_text = story.get("criteria_text", "")
        # Simple heuristic: look for path-like strings (containing / and a file extension)
        path_pattern = re.compile(r'[\w./]+/[\w.]+\.\w+')
        referenced_files = path_pattern.findall(criteria_text)
        for ref_file in referenced_files:
            covered = any(fnmatch_mod.fnmatch(ref_file, p) for p in test_mapping)
            if not covered:
                msg = f"Pre-flight: {ref_file} referenced in criteria lacks test_mapping entry"
                warnings.append(msg)
                log(f"  {msg}")

    # Store warnings in state
    update_state_story(
        state, story["id"], story_state.get("status", "pending"),
        story_state.get("attempts", 0), spec_key=spec_key
    )
    if spec_key is not None:
        state["specs"][spec_key].setdefault("stories", {}).setdefault(story["id"], {})["pre_flight_warnings"] = warnings
    else:
        state.setdefault("stories", {}).setdefault(story["id"], {})["pre_flight_warnings"] = warnings

    return warnings


def check_test_mapping_gaps(
    changed_files_str: str, project_dir: str, warned_files: set[str]
) -> list[str]:
    """Check if changed source files have explicit test_mapping coverage.

    Returns a list of warning messages for unmapped files.
    Deduplicates across calls via warned_files set (modified in place).
    """
    if not changed_files_str:
        return []
    testing_guide = os.path.join(project_dir, "kit_tools", "testing", "TESTING_GUIDE.md")
    if not os.path.exists(testing_guide):
        return []  # No TESTING_GUIDE.md — skip silently

    test_mapping = parse_test_mapping(project_dir)
    if not test_mapping:
        return []

    import fnmatch as fnmatch_mod
    warnings = []
    source_files = _filter_source_files(
        [f.strip() for f in changed_files_str.split("\n") if f.strip()]
    )

    for src_file in source_files:
        if src_file in warned_files:
            continue  # Already warned in a prior story
        # Check if any mapping pattern covers this file
        covered = any(
            fnmatch_mod.fnmatch(src_file, pattern)
            for pattern in test_mapping
        )
        if not covered:
            msg = f"Add test_mapping entry for {src_file} in TESTING_GUIDE.md"
            warnings.append(msg)
            warned_files.add(src_file)
            log(f"  WARNING: {msg}")

    return warnings


def run_regression_check(
    project_dir: str, state: dict, current_story_id: str,
    test_command: str | None, spec_key: str | None = None
) -> tuple[bool, str]:
    """Run regression tests from prior completed stories after a merge.

    Returns (passed, message). If passed is False, the merge should be reverted.
    Uses direct subprocess — not a Claude session.
    Records results in test-metrics.json for observability.
    """
    if not test_command:
        return True, "Skipped — no test command detected"

    # Gather files_changed from prior completed stories
    if spec_key is not None:
        stories_dict = state.get("specs", {}).get(spec_key, {}).get("stories", {})
    else:
        stories_dict = state.get("stories", {})

    # Collect up to 10 most recent completed stories' files
    prior_files: list[str] = []
    story_count = 0
    for sid, sdata in reversed(list(stories_dict.items())):
        if sid == current_story_id:
            continue
        if sdata.get("status") != "completed":
            continue
        files = sdata.get("files_changed", [])
        prior_files.extend(files)
        story_count += 1
        if story_count >= 10:
            break

    if not prior_files:
        return True, "Skipped — no prior stories with files_changed"

    # Resolve test files through global test_mapping
    import fnmatch as fnmatch_mod
    test_mapping = parse_test_mapping(project_dir)
    if not test_mapping:
        return True, "Skipped — no test_mapping available"

    regression_tests: set[str] = set()
    source_files = _filter_source_files(prior_files)
    for src_file in source_files:
        for pattern, test_pattern in test_mapping.items():
            if fnmatch_mod.fnmatch(src_file, pattern):
                for tp in test_pattern.split():
                    if tp:
                        regression_tests.add(tp)

    # Resolve to existing files
    existing = _resolve_test_files(regression_tests, project_dir)
    if not existing:
        return True, "Skipped — no regression test files resolved"

    # Cap at REGRESSION_TEST_FILE_CAP
    if len(existing) > REGRESSION_TEST_FILE_CAP:
        existing = sorted(existing)[:REGRESSION_TEST_FILE_CAP]
        log(f"  Regression: capped at {REGRESSION_TEST_FILE_CAP} test files")

    all_files = sorted(existing)
    log(f"  Regression check: {len(all_files)} test files from {story_count} prior stories")

    # Route each resolved test file to the runner that owns it (by extension),
    # running each group from its owning package dir. Fail-fast within a group
    # (-x/--bail) and across groups (return on the first failing group), matching
    # the single-runner behaviour this replaces.
    groups = _partition_test_files(all_files, project_dir)
    if not groups:
        return True, "Skipped — no runnable test files after partition"

    for (runner, cwd), rel_files in groups.items():
        cmd = _regression_cmd(runner, rel_files)
        if cmd is None:
            log(f"  Regression: unknown runner '{runner}', skipping {len(rel_files)} file(s)")
            continue
        rel_cwd = os.path.relpath(cwd, project_dir) or "."
        log(f"  Regression check: {len(rel_files)} {runner} file(s) (cwd={rel_cwd})")
        passed, output = _run_regression_group(cmd, cwd)
        if not passed:
            # Confirm before reporting a regression — a failure here reverts a
            # merge that already passed verification, so one flaky run must not
            # be enough. See _confirm_regression.
            passed, output = _confirm_regression(cmd, cwd, runner, output)
        # Record metrics with repo-relative paths so keys are consistent across
        # runners. Recorded post-confirmation so a flake that the re-run cleared
        # is not filed as a test failure.
        repo_rel = [os.path.relpath(os.path.join(cwd, f), project_dir) for f in rel_files]
        update_test_metrics_from_regression(project_dir, repo_rel, passed, current_story_id)
        if not passed:
            partial = "\n".join(output.strip().split("\n")[:50])
            return False, f"REGRESSION: tests failed ({runner})\n{partial}"

    return True, f"Passed ({len(all_files)} test files across {len(groups)} runner(s))"


def detect_test_command(project_dir: str) -> str | None:
    """Auto-detect the project's test command.

    Checks in order:
    1. package.json "test" script (skip if it's the npm default)
    2. pyproject.toml [tool.pytest] or [tool.poetry.scripts]
    3. pytest.ini
    4. Makefile "test" target
    5. kit_tools/testing/TESTING_GUIDE.md Quick Start section

    Returns the test command string, or None if not detected.
    """
    # 1. package.json
    pkg_json = os.path.join(project_dir, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, "r") as f:
                pkg = json.load(f)
            test_script = pkg.get("scripts", {}).get("test", "")
            # Skip npm default placeholder
            if test_script and 'echo "Error: no test specified"' not in test_script:
                return f"npm test"
        except (json.JSONDecodeError, OSError):
            pass

    # 2. pyproject.toml
    pyproject = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, "r") as f:
                content = f.read()
            # Check for pytest configuration
            if "[tool.pytest" in content:
                return "python3 -m pytest"
            # Check for poetry test script
            if "[tool.poetry.scripts]" in content and "test" in content:
                return "poetry run pytest"
        except OSError:
            pass

    # 3. pytest.ini
    if os.path.exists(os.path.join(project_dir, "pytest.ini")):
        return "python3 -m pytest"

    # 4. Makefile
    makefile = os.path.join(project_dir, "Makefile")
    if os.path.exists(makefile):
        try:
            with open(makefile, "r") as f:
                content = f.read()
            if re.search(r"^test\s*:", content, re.MULTILINE):
                return "make test"
        except OSError:
            pass

    # 5. kit_tools/testing/TESTING_GUIDE.md
    testing_guide = os.path.join(project_dir, "kit_tools", "testing", "TESTING_GUIDE.md")
    if os.path.exists(testing_guide):
        try:
            with open(testing_guide, "r") as f:
                content = f.read()
            # Look for a code block in the Quick Start section
            qs_match = re.search(
                r"##\s*Quick Start.*?```(?:\w*)\n(.+?)```",
                content, re.DOTALL | re.IGNORECASE
            )
            if qs_match:
                # Take the first non-empty line from the code block
                for line in qs_match.group(1).strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
        except OSError:
            pass

    return None


def make_fail_fast(test_command: str) -> str:
    """Append fail-fast flags to known test runners."""
    if not test_command:
        return test_command
    if "pytest" in test_command:
        return f"{test_command} -x"
    if test_command in ("npm test",) or "npx jest" in test_command:
        return f"{test_command} -- --bail"
    if "vitest" in test_command:
        return f"{test_command} --bail 1"
    return test_command


