"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import re
import signal
import subprocess
import threading
import time
from typing import NamedTuple

from .specs import parse_spec_frontmatter
from .utils import log


class SessionResult(NamedTuple):
    """Outcome of one `claude -p` session.

    `output` is the agent's final text on success, or a `SESSION_ERROR*` marker
    on failure (callers still gate on `is_session_error(result.output)`).
    `usage` is the real token usage dict from `--output-format json` (keys like
    `input_tokens`, `output_tokens`, cache variants) or None if unavailable;
    `cost_usd` is the CLI-reported cost or None. None means "not measured" —
    callers must never present a missing value as zero cost (honesty guardrail).
    """
    output: str
    usage: dict | None = None
    cost_usd: float | None = None


def _parse_session_json(stdout: str) -> tuple[str, dict | None, float | None]:
    """Parse a `--output-format json` session result into (text, usage, cost).

    Falls back to (raw_stdout, None, None) if the output isn't the expected JSON
    envelope, so a CLI format change degrades to estimate-only rather than
    breaking the run.
    """
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return stdout, None, None
    if not isinstance(data, dict):
        return stdout, None, None
    text = data.get("result")
    if not isinstance(text, str):
        text = stdout
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    cost = data.get("total_cost_usd")
    cost = float(cost) if isinstance(cost, (int, float)) else None
    # An agent-level failure can return is_error=true at exit 0 (e.g. context
    # overflow, an unrecoverable tool error mid-session). Surface it as a session
    # error so callers retry/classify instead of treating the failure text as a
    # successful result. Usage/cost are still real — keep them.
    if data.get("is_error"):
        text = f"SESSION_ERROR: agent-level error (is_error): {text[:500]}"
    return text, usage, cost


def usage_tokens(usage: dict | None) -> tuple[int | None, int | None]:
    """Collapse a Claude usage dict to (input_tokens, output_tokens).

    Input includes cache-creation and cache-read tokens so the figure reflects
    the real billed input. Returns (None, None) when usage is absent.
    """
    if not isinstance(usage, dict):
        return None, None
    inp = (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )
    out = usage.get("output_tokens") or 0
    return int(inp), int(out)


SESSION_TIMEOUT = 900  # 15 minutes per claude session
IMPL_SESSION_TIMEOUT = 900  # implementation sessions
VERIFY_SESSION_TIMEOUT = 600  # verification sessions (smaller task)
NETWORK_RETRY_WAIT = 30  # seconds between network retries
NETWORK_MAX_RETRIES = 3
# Independent wall-clock watchdog (issue #20). `proc.communicate(timeout=...)`
# measures its deadline against a *monotonic* clock, which on most platforms
# does not advance while the host is suspended (sleep/hibernate/battery death).
# So a child whose network socket died with the host can outlive its timeout
# indefinitely — the orchestrator stays blocked in communicate() with no crash
# signal. The watchdog thread below is a belt-and-braces backstop that bounds
# the child's life against WALL-clock time (which *does* include suspend), so a
# stalled child is force-killed and the normal session-error/retry path fires.
WATCHDOG_GRACE = 300  # seconds of slack over the session timeout before we kill
WATCHDOG_POLL_INTERVAL = 30  # how often the watchdog re-checks wall-clock age
PERMANENT_ERROR_KEYWORDS = ["context", "too long", "token limit", "input.*too.*large", "maximum.*context"]
IMPL_RESULT_FILE = os.path.join("kit_tools", ".story-impl-result.json")
VERIFY_RESULT_FILE = os.path.join("kit_tools", ".story-verify-result.json")


def _is_permanent_error(stderr_text: str) -> bool:
    """Check if a session error is permanent (not worth retrying)."""
    lower = stderr_text.lower()
    return any(re.search(kw, lower) for kw in PERMANENT_ERROR_KEYWORDS)


def is_session_error(output: str) -> bool:
    """Check if output represents any kind of session error."""
    return output.startswith("SESSION_ERROR:") or output.startswith("SESSION_ERROR_PERMANENT:")


def get_size_timeouts(spec_path: str | None) -> tuple[int, int]:
    """Read optional size hint from spec frontmatter and return (impl_timeout, verify_timeout).

    Supported sizes: S, M (default), L, XL. Unrecognized values log a warning and use M.
    """
    size_map = {
        "S": (600, 300),
        "M": (IMPL_SESSION_TIMEOUT, VERIFY_SESSION_TIMEOUT),
        "L": (1500, 900),
        "XL": (1800, 1200),
    }
    if not spec_path or not os.path.exists(spec_path):
        return size_map["M"]
    fm = parse_spec_frontmatter(spec_path)
    if not fm:
        # No parseable frontmatter — surface it rather than silently using M.
        # (This is what masked the size: hint being ignored for every
        # template-generated spec; the parser now skips leading comments.)
        log(f"  WARNING: no parseable frontmatter in {os.path.basename(spec_path)} "
            f"— using M-size timeouts (any size: hint ignored)")
        return size_map["M"]
    size = str(fm.get("size", "M")).upper()
    if size in size_map:
        return size_map[size]
    log(f"  WARNING: Unrecognized size '{fm.get('size')}' in spec frontmatter — using M defaults")
    return size_map["M"]


# Process groups of currently-running child `claude` sessions. Each child is
# spawned in its own session (start_new_session=True) so a timeout can kill the
# whole tree; we also track the live pgid(s) here so the orchestrator's OWN
# signal/exit handlers can reap the child when the orchestrator is stopped
# (Ctrl+C, SIGTERM/SIGHUP, `pkill execute_orchestrator.py`, tmux kill). Without
# this the child is orphaned (it's in a separate process group), keeps running,
# and finishes writing partial/unverified work — re-dirtying the worktree after
# teardown/cleanup.
_ACTIVE_CHILD_PGIDS: set[int] = set()


def kill_active_child_sessions() -> None:
    """Reap any still-running child `claude` process groups.

    Safe to call from a signal handler or atexit, and idempotent — used by the
    orchestrator's stop/teardown path so stopping the orchestrator also stops
    its child session.
    """
    for pgid in list(_ACTIVE_CHILD_PGIDS):
        _kill_process_group(pgid)
        _ACTIVE_CHILD_PGIDS.discard(pgid)


def _kill_process_group(pgid: int) -> None:
    """Kill a process group gracefully (SIGTERM), then forcefully (SIGKILL).

    Sends SIGTERM first to allow child processes to clean up, then SIGKILL
    after a short grace period to ensure nothing lingers. Silently ignores
    errors if the process group is already gone.
    """
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return  # Already gone
    time.sleep(0.5)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass  # Terminated during grace period


def _start_session_watchdog(proc: "subprocess.Popen", timeout: int,
                            stop_event: "threading.Event") -> threading.Thread:
    """Bound a child session's lifetime against WALL-clock time (issue #20).

    `proc.communicate(timeout=...)` can fail to fire when the host suspends,
    because its deadline is measured against a monotonic clock that freezes
    during sleep/hibernate. The child's network socket dies with the host, so
    the session never completes and the orchestrator blocks in communicate()
    forever with no crash signal.

    This watchdog runs in a daemon thread and polls wall-clock elapsed time
    every ``WATCHDOG_POLL_INTERVAL`` seconds. Wall time *does* include suspend,
    so after resume the thread notices — within one poll interval of awake time
    — that ``timeout + WATCHDOG_GRACE`` has been exceeded and force-terminates
    the child's process tree. That unblocks communicate(), which then returns
    via the normal timeout/error path and the session is retried like any other
    stall. ``stop_event`` is set by the caller the moment communicate() returns
    normally, so the watchdog never kills a healthy child.
    """
    deadline = time.time() + timeout + WATCHDOG_GRACE

    def _watch() -> None:
        while not stop_event.wait(WATCHDOG_POLL_INTERVAL):
            if proc.poll() is not None:
                return  # child already exited on its own
            if time.time() >= deadline:
                log(f"  WATCHDOG: child {proc.pid} exceeded wall-clock budget "
                    f"({timeout}s timeout + {WATCHDOG_GRACE}s grace) — likely "
                    f"stalled across a host suspend; terminating process tree")
                _kill_process_group(proc.pid)
                try:
                    proc.kill()
                except OSError:
                    pass
                return

    t = threading.Thread(target=_watch, name="session-watchdog", daemon=True)
    t.start()
    return t


def run_claude_session(
    prompt: str, project_dir: str, timeout: int = SESSION_TIMEOUT,
    model: str | None = None,
) -> SessionResult:
    """Execute a claude -p session and capture output + real token usage.

    Retries up to NETWORK_MAX_RETRIES times for network errors. Returns a
    `SessionResult`: on success `.output` is the agent's final text and
    `.usage`/`.cost_usd` carry the real figures parsed from `--output-format
    json`; on failure `.output` is a SESSION_ERROR/SESSION_ERROR_PERMANENT
    marker and usage/cost are None.

    Args:
        model: Optional model alias ("sonnet", "opus") or full model ID,
            passed via `--model`. `None` uses the claude CLI default.
    """
    clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    # `--output-format json` wraps the final text in an envelope that also
    # carries real `usage` + `total_cost_usd`. The orchestrator reads agent
    # results from result *files*, not this stdout, so the only consumers of
    # this string are SESSION_ERROR detection and the char-count fallback —
    # both unaffected by the wrapping (we unwrap `.result` on success).
    cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions",
           "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])

    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_dir,
                env=clean_env,
                start_new_session=True,
            )
            # Track the live child's process group so the orchestrator's signal/
            # exit handlers can reap it if the orchestrator is stopped mid-session.
            _ACTIVE_CHILD_PGIDS.add(proc.pid)

            # Independent wall-clock backstop for host-suspend stalls (issue #20).
            _watchdog_stop = threading.Event()
            _start_session_watchdog(proc, timeout, _watchdog_stop)

            try:
                try:
                    stdout, stderr_out = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Kill the entire process group (claude + all children like pytest, node, etc.)
                    _kill_process_group(proc.pid)
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    # Bound the final wait — if SIGKILL didn't take (zombie,
                    # uninterruptible sleep, permissions), we prefer a leaked PID
                    # over a hung orchestrator.
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        log(f"  WARNING: subprocess {proc.pid} did not exit after SIGKILL — continuing with process leaked")
                    return SessionResult(f"SESSION_ERROR: Timed out after {timeout}s")

                # Session finished — kill any orphaned children in the process group
                _kill_process_group(proc.pid)

                if proc.returncode == 0:
                    text, usage, cost = _parse_session_json(stdout)
                    return SessionResult(text, usage, cost)

                stderr = stderr_out.strip()
                is_network = any(kw in stderr.lower() for kw in ("network", "connection", "timeout", "econnrefused"))

                # Retry network errors (unless this is the last attempt)
                if is_network and attempt < NETWORK_MAX_RETRIES:
                    log(f"  Network error (attempt {attempt}/{NETWORK_MAX_RETRIES}), retrying in {NETWORK_RETRY_WAIT}s...")
                    time.sleep(NETWORK_RETRY_WAIT)
                    continue

                # Final network attempt or non-network error — return error
                if is_network:
                    return SessionResult(f"SESSION_ERROR: Network error after {NETWORK_MAX_RETRIES} attempts\n{stderr}")
                prefix = "SESSION_ERROR_PERMANENT" if _is_permanent_error(stderr) else "SESSION_ERROR"
                return SessionResult(f"{prefix}: Exit code {proc.returncode}\n{stderr}\n{stdout}")
            finally:
                _watchdog_stop.set()
                _ACTIVE_CHILD_PGIDS.discard(proc.pid)

        except FileNotFoundError:
            # `claude` missing can be transient on some hosts (a PATH not yet
            # refreshed, an antivirus/file lock, a slow network drive). Treating
            # the first miss as permanent burned the story with zero retries and
            # bypassed guarded mode's pause (issue #15). Retry like a network
            # error; only escalate to permanent once retries are exhausted.
            if attempt < NETWORK_MAX_RETRIES:
                log(f"  'claude' not found (attempt {attempt}/{NETWORK_MAX_RETRIES}) — "
                    f"retrying in {NETWORK_RETRY_WAIT}s (transient PATH/filesystem issue?)...")
                time.sleep(NETWORK_RETRY_WAIT)
                continue
            return SessionResult(
                "SESSION_ERROR_PERMANENT: 'claude' command not found after "
                f"{NETWORK_MAX_RETRIES} attempts. Ensure Claude CLI is installed and in PATH."
            )

    # Should not reach here, but safety net
    return SessionResult("SESSION_ERROR: All retries exhausted")


def get_impl_result_path(project_dir: str) -> str:
    """Return absolute path to the implementation result file."""
    return os.path.join(project_dir, IMPL_RESULT_FILE)


def get_verify_result_path(project_dir: str) -> str:
    """Return absolute path to the verification result file."""
    return os.path.join(project_dir, VERIFY_RESULT_FILE)


def clean_result_files(project_dir: str) -> None:
    """Remove result files before a new attempt to prevent stale reads."""
    for path in [get_impl_result_path(project_dir), get_verify_result_path(project_dir)]:
        if os.path.exists(path):
            os.remove(path)


def _extract_json_from_text(text: str) -> str:
    """Extract JSON from text that may contain markdown fences or preamble.

    Agents sometimes wrap JSON in ```json ... ``` fences or add extra text.
    """
    # Try stripping markdown fences first
    fence_match = re.search(r"```(?:json)?\s*\n({.*?})\s*\n```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    # Try finding the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)
    return text


def read_json_result(file_path: str) -> tuple[dict | None, str]:
    """Read and parse a JSON result file.

    Returns (result_dict, error_message). On success, error_message is empty.
    On failure, result_dict is None and error_message explains why.

    Handles common agent output issues: markdown fences, preamble text,
    trailing commas.
    """
    if not os.path.exists(file_path):
        return None, f"Result file not found: {os.path.basename(file_path)}"
    try:
        with open(file_path, "r") as f:
            raw = f.read()
    except OSError as e:
        return None, f"Could not read {os.path.basename(file_path)}: {e}"

    # First try direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data, ""
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from surrounding text (markdown fences, preamble)
    extracted = _extract_json_from_text(raw)
    try:
        data = json.loads(extracted)
        if isinstance(data, dict):
            log(f"  Note: extracted JSON from non-clean output in {os.path.basename(file_path)}")
            return data, ""
    except json.JSONDecodeError:
        pass

    # Try fixing trailing commas (common LLM output issue)
    cleaned = re.sub(r",\s*([\]}])", r"\1", extracted)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            log(f"  Note: fixed trailing commas in {os.path.basename(file_path)}")
            return data, ""
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in {os.path.basename(file_path)}: {e}\nFirst 200 chars: {raw[:200]}"

    return None, f"Result file is not a JSON object: {os.path.basename(file_path)}"


def read_implementation_result(project_dir: str) -> tuple[dict | None, str]:
    """Read the implementation result JSON file.

    Returns (result_dict, error_message).
    """
    result, error = read_json_result(get_impl_result_path(project_dir))
    if result is not None:
        if "story_id" not in result:
            return None, "Implementation result missing 'story_id' field"
        if result.get("status") not in ("complete", "partial", "failed"):
            return None, f"Implementation result has invalid 'status': {result.get('status')}"
        for optional in ("learnings", "issues", "files_changed"):
            if optional not in result:
                log(f"  Note: implementation result missing optional field '{optional}'")
    return result, error


def read_verification_result(project_dir: str) -> tuple[dict | None, str]:
    """Read the verification result JSON file.

    Returns (result_dict, error_message).
    Expected keys: story_id, verdict, criteria, overall_notes, recommendations
    """
    result, error = read_json_result(get_verify_result_path(project_dir))
    if result is not None:
        # Normalize verdict to lowercase
        if "verdict" in result:
            result["verdict"] = str(result["verdict"]).lower()
        else:
            return None, "Verification result missing 'verdict' field"
        if result["verdict"] not in ("pass", "pass_with_warnings", "fail"):
            return None, f"Verification result has invalid 'verdict': {result['verdict']}"
        if not isinstance(result.get("criteria"), list):
            return None, "Verification result missing or invalid 'criteria' list"
        # Validate warnings field if present (must be array of strings)
        if "warnings" in result:
            if not isinstance(result["warnings"], list):
                log(f"  Note: verification result has non-list 'warnings' field — discarding")
                result["warnings"] = []
            else:
                result["warnings"] = [str(w) for w in result["warnings"] if w]
        for optional in ("overall_notes", "recommendations"):
            if optional not in result:
                log(f"  Note: verification result missing optional field '{optional}'")
    return result, error


def extract_learnings_from_results(
    impl_result: dict | None, verify_result: dict | None
) -> list[str]:
    """Extract learnings from file-based implementation and verification results."""
    learnings = []

    if impl_result:
        for learning in impl_result.get("learnings", []):
            if learning:
                learnings.append(str(learning))
        for issue in impl_result.get("issues", []):
            if issue:
                learnings.append(f"Issue: {issue}")

    if verify_result:
        if verify_result.get("recommendations"):
            learnings.append(f"Verifier: {verify_result['recommendations']}")
        if verify_result.get("overall_notes"):
            learnings.append(f"Verifier note: {verify_result['overall_notes']}")

    return learnings


