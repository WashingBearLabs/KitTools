"""Merge-base test baseline capture and diffing (issue #6).

The orchestrator owns the merge base, the branch, and the test invocation, so it
is the only component that can answer *"did this epic break this test, or was it
already red before we started?"*. Nothing else did — the final gate treated any
non-zero test exit as failure and could not distinguish pre-existing failures
from ones the epic introduced, so a single red test at the merge base sank final
validation for reasons the epic never caused.

This module captures a **baseline** at pre-flight (before the first story
commits, when the worktree HEAD still equals the merge base) by running the
project's own test command once and recording which tests already fail. The
final-validation prompt then carries that list so the validator reports only
*new* failures as blocking and lists pre-existing ones as informational.

Design notes:
* Capture is **best-effort and never fatal** — a missing/failing runner records
  a ``skipped`` status rather than aborting the run. A red baseline is the whole
  point (we want to know), so a non-zero exit is a normal, recorded outcome.
* Only runs on a **fresh** launch (not a resume), because after stories have
  committed, HEAD no longer equals the merge base.
* Node-id extraction is reliable for **pytest** (the dominant case and the one
  in the issue). For other runners we still record the pass/fail exit code so a
  red baseline is surfaced at launch, but mark the result non-diffable at the
  node level.
* The child is spawned in its own session/process group exactly like the
  regression runner, so a timeout can kill the whole tree.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess

from .git_ops import get_head_commit
from .sessions import _kill_process_group
from .tests_metrics import detect_test_command
from .utils import log, now_iso

# A full suite can be slow; bound it generously but never block forever. A
# timeout records a ``skipped`` baseline (unknown), not a red one.
BASELINE_TIMEOUT = 900  # seconds

# pytest prints one `FAILED path::test - reason` (and `ERROR path::test`) line
# per failing/erroring node in its short summary. We force that summary on with
# `-rfE` so the lines are always present, then scrape node ids from them.
_PYTEST_NODE_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)


def _split_command(cmd: str) -> list[str]:
    """Split a test-command string into argv."""
    return shlex.split(cmd)


def _augment_pytest(argv: list[str]) -> list[str]:
    """Force pytest's failure summary so node ids are always emitted."""
    if any("pytest" in part for part in argv) and "-rfE" not in argv:
        return argv + ["-rfE"]
    return argv


def _parse_pytest_failures(output: str) -> list[str]:
    """Extract failing/erroring node ids from pytest output (deduped, ordered)."""
    seen: dict[str, None] = {}
    for node in _PYTEST_NODE_RE.findall(output):
        seen.setdefault(node, None)
    return list(seen)


def _run_suite(project_dir: str, argv: list[str]) -> tuple[int | None, str]:
    """Run a test ``argv`` in ``project_dir``. Returns ``(exit_code, output)``.

    ``exit_code`` is ``None`` when the runner could not produce a verdict at all
    (missing binary or timeout); ``output`` then carries a short reason token
    (``"runner_unavailable"`` / ``"timeout"``) instead of test output. Spawned in
    its own session so a timeout can kill the whole tree.
    """
    try:
        proc = subprocess.Popen(
            argv, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", start_new_session=True,
        )
    except OSError:
        return None, "runner_unavailable"
    try:
        stdout, stderr_out = proc.communicate(timeout=BASELINE_TIMEOUT)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return None, "timeout"
    _kill_process_group(proc.pid)
    return proc.returncode, (stdout or "") + (stderr_out or "")


def capture_baseline(project_dir: str, config: dict | None = None) -> dict:
    """Run the project's test command once at the current HEAD (the merge base
    at pre-flight) and return a baseline record.

    The returned dict always carries a ``status`` field:

    * ``"clean"`` — the suite ran and everything passed (exit 0).
    * ``"red"`` — the suite ran and some tests failed (exit non-zero). For
      pytest, ``failing_node_ids`` lists them; ``diffable`` is True.
    * ``"skipped"`` — no test command detected, the runner was missing, or the
      run timed out. The baseline is unknown; final validation proceeds as it
      did before (no pre-existing-failure allowance).

    Never raises — capture failures degrade to ``"skipped"``.
    """
    command = detect_test_command(project_dir)
    captured_at = now_iso()
    try:
        commit = get_head_commit(project_dir)
    except Exception:
        commit = ""

    if not command:
        log("  Baseline: no test command detected — skipping baseline capture")
        return {
            "status": "skipped",
            "reason": "no_test_command",
            "captured_at": captured_at,
            "commit": commit,
            "command": None,
            "failing_node_ids": [],
            "diffable": False,
        }

    argv = _augment_pytest(_split_command(command))
    is_pytest = any("pytest" in part for part in argv)
    log(f"  Baseline: running merge-base test suite ({command})...")

    exit_code, output = _run_suite(project_dir, argv)
    if exit_code is None:
        reason = output  # "runner_unavailable" | "timeout"
        if reason == "timeout":
            log(f"  Baseline: timed out after {BASELINE_TIMEOUT}s — skipping baseline")
        else:
            log(f"  Baseline: runner unavailable ({argv[0]}) — skipping baseline")
        return {
            "status": "skipped",
            "reason": reason,
            "captured_at": captured_at,
            "commit": commit,
            "command": command,
            "failing_node_ids": [],
            "diffable": False,
        }

    if exit_code == 0:
        log("  Baseline: merge base is GREEN (all tests pass)")
        return {
            "status": "clean",
            "captured_at": captured_at,
            "commit": commit,
            "command": command,
            "exit_code": 0,
            "failing_node_ids": [],
            "diffable": is_pytest,
        }

    failing = _parse_pytest_failures(output) if is_pytest else []
    diffable = is_pytest and bool(failing)
    if diffable:
        log(f"  Baseline: merge base is RED — {len(failing)} pre-existing "
            f"failure(s); these will be excluded from final validation")
    else:
        log(f"  Baseline: merge base test command exited {exit_code} "
            f"(non-diffable — node ids unavailable for this runner)")
    return {
        "status": "red",
        "captured_at": captured_at,
        "commit": commit,
        "command": command,
        "exit_code": exit_code,
        "failing_node_ids": failing,
        "diffable": diffable,
    }


def baseline_launch_note(baseline: dict) -> str | None:
    """One-line human summary for the launch log / notification, or None when
    there is nothing worth surfacing (clean or skipped baseline)."""
    if not baseline or baseline.get("status") != "red":
        return None
    n = len(baseline.get("failing_node_ids") or [])
    if baseline.get("diffable") and n:
        return (f"Starting from a RED baseline: {n} test(s) already fail at the "
                f"merge base. These are pre-existing and will be excluded from "
                f"final validation — consider fixing them separately.")
    return ("Starting from a RED baseline: the test suite already fails at the "
            "merge base (exit "
            f"{baseline.get('exit_code', 'non-zero')}). Node ids were not "
            "parseable for this runner, so final validation cannot auto-exclude "
            "them — review before trusting the final gate.")


def format_baseline_for_prompt(baseline: dict) -> str:
    """Text injected into the epic-wide / final validation prompt so the
    validator can distinguish pre-existing failures from epic-introduced ones.
    Returns an empty string when there is nothing useful to say."""
    if not baseline or baseline.get("status") != "red":
        return ""
    failing = baseline.get("failing_node_ids") or []
    if baseline.get("diffable") and failing:
        listed = "\n".join(f"  - {n}" for n in failing)
        return (
            "\n\nBASELINE (pre-existing failures at the merge base): the "
            f"following {len(failing)} test(s) ALREADY FAILED before this epic "
            "began and must be treated as pre-existing, NOT as blocking "
            "regressions. Report them separately as informational; only NEW "
            f"failures (not in this list) may block the gate:\n{listed}"
        )
    return (
        "\n\nBASELINE: the project's test suite already failed at the merge base "
        f"(exit {baseline.get('exit_code', 'non-zero')}) before this epic began, "
        "but individual failing tests could not be enumerated for this runner. "
        "Do not treat a red full-suite result as an epic regression without "
        "confirming the specific failures are new; focus the gate on the epic's "
        "own acceptance criteria and diff."
    )


def diff_main_vs_worktree(main_repo: str, worktree_dir: str,
                          worktree_baseline: dict) -> dict | None:
    """Diff the test result of the main checkout against the worktree (issue #10).

    Worktree isolation is an excellent latent-bug detector: the execution
    worktree is built from **committed** state, so a test that passes in the
    user's live checkout but fails in the worktree means *something the build
    depends on is not committed* (a gitignored or untracked file the tests read).
    That is a high-value diagnosis and a far clearer signal than the downstream
    failures it otherwise surfaces as.

    This reuses the worktree run already captured for the #6 baseline and only
    adds the *second* (main-checkout) run, so the marginal cost is one extra
    suite invocation. Opt-in (the caller gates on ``config["verify_baseline"]``)
    because it roughly doubles pre-flight test time.

    Returns a dict describing the discrepancy, or ``None`` when there is nothing
    to report (identical results, non-diffable runner, or the main run could not
    be produced). Never raises.
    """
    command = (worktree_baseline or {}).get("command")
    if not command or not worktree_baseline.get("diffable"):
        # No enumerable per-test result to compare (non-pytest / skipped).
        return None
    worktree_failures = set(worktree_baseline.get("failing_node_ids") or [])
    if not worktree_failures:
        # Worktree is green — nothing can be "only in the worktree", so the
        # extra main-checkout run would be pure cost with no possible signal.
        return None
    if not main_repo or os.path.realpath(main_repo) == os.path.realpath(worktree_dir):
        return None

    argv = _augment_pytest(_split_command(command))
    log(f"  Baseline diff: re-running the suite in the main checkout ({command})...")
    exit_code, output = _run_suite(main_repo, argv)
    if exit_code is None:
        log("  Baseline diff: main-checkout run could not be produced — skipping diff")
        return None

    main_failures = set(_parse_pytest_failures(output))
    # The valuable signal: green in the main checkout, red in the worktree.
    only_in_worktree = sorted(worktree_failures - main_failures)
    if not only_in_worktree:
        log("  Baseline diff: no committed-vs-working-tree discrepancy detected")
        return None

    log(f"  Baseline diff: {len(only_in_worktree)} test(s) pass in your checkout "
        f"but fail in the execution worktree — likely an uncommitted/gitignored "
        f"dependency")
    return {
        "command": command,
        "only_fail_in_worktree": only_in_worktree,
        "also_fail_in_main": sorted(worktree_failures & main_failures),
    }


def baseline_diff_note(diff: dict | None) -> str | None:
    """Human summary of a main-vs-worktree discrepancy for the launch log /
    notification, or None when there is nothing to report."""
    if not diff:
        return None
    nodes = diff.get("only_fail_in_worktree") or []
    if not nodes:
        return None
    listed = ", ".join(nodes[:5]) + (" …" if len(nodes) > 5 else "")
    return (
        f"Baseline differs between your checkout and the execution worktree: "
        f"{len(nodes)} test(s) pass in your checkout but FAIL in the worktree "
        f"({listed}). This usually means a file the tests depend on is gitignored "
        f"or untracked — commit it (or fix the .gitignore rule) so the worktree "
        f"and your checkout agree."
    )
