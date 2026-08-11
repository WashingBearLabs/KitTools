"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import platform
import re
import resource
import subprocess
import threading
import time
from datetime import datetime, timezone

from .events import log_event, write_notification
from .state import save_state, update_state_story
from .utils import _atomic_json_write, log, now_iso, run_git

PAUSE_POLL_INTERVAL = 10  # seconds between pause file checks
PAUSE_MAX_WAIT = 86400  # 24 hours max pause
PAUSE_LOG_INTERVAL = 60  # log reminder every minute
HEALTH_FILE = os.path.join("kit_tools", "specs", ".execution-health.json")
CONTROL_FILE = os.path.join("kit_tools", "specs", ".execution-control.json")
STOP_FILE = os.path.join("kit_tools", ".supervisor_stop")
MAX_ORCHESTRATOR_DURATION = 86400  # 24 hours — safety net
HEARTBEAT_INTERVAL = 60  # seconds between background heartbeat refreshes

# Serializes writes to the health file between the main thread (full snapshots
# at attempt boundaries) and the heartbeat thread (heartbeat-only refreshes),
# so a refresh can never clobber a snapshot written concurrently.
_HEALTH_LOCK = threading.Lock()


def get_health_path(config: dict) -> str:
    """Return absolute path to the health snapshot file."""
    return os.path.join(config["project_dir"], HEALTH_FILE)


def get_control_path(config: dict) -> str:
    """Return absolute path to the supervisor control file."""
    return os.path.join(config["project_dir"], CONTROL_FILE)


def get_stop_path(config: dict) -> str:
    """Return absolute path to the supervisor-stop marker."""
    return os.path.join(config["project_dir"], STOP_FILE)


def signal_supervisor_stop(config: dict, reason: str) -> None:
    """Drop a deterministic marker telling the supervisor cron to stop polling.

    Written when the orchestrator EXITS (nothing left to supervise) or enters a
    block only a human can clear (critical-validation review). Deliberately NOT
    written for supervisor-healable pauses (guarded retry-exhaustion) — those
    keep the supervisor alive so it can skip/split and resume. `execution-status`
    checks this first and `CronDelete`s itself when present. Best-effort."""
    try:
        path = get_stop_path(config)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"reason": reason, "at": now_iso()}, f)
    except OSError:
        pass


def clear_supervisor_stop(config: dict) -> None:
    """Remove a stale stop marker so a fresh/resumed run's supervisor isn't
    killed by a prior run's marker. Best-effort."""
    try:
        os.remove(get_stop_path(config))
    except OSError:
        pass


def _get_memory_usage_mb() -> float:
    """Get current process memory usage in MB using stdlib only."""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is in bytes on Linux, kilobytes on macOS
        if platform.system() == "Darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except Exception:
        return -1.0


def _get_child_pids() -> list[int]:
    """Get PIDs of child processes. Best-effort — returns empty on failure."""
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(os.getpid())],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return []


def write_health_snapshot(
    config: dict, state: dict,
    current_story_id: str | None = None,
    current_attempt: int = 0,
    event: str = "heartbeat",
) -> None:
    """Write a health snapshot for the supervisor to read.

    Called after every story attempt and at key lifecycle points.
    The supervisor (OG Claude session) reads this file to assess orchestrator health.
    """
    path = get_health_path(config)
    with _HEALTH_LOCK:
        _write_health_snapshot_locked(path, state, current_story_id,
                                      current_attempt, event)


def _write_health_snapshot_locked(
    path: str, state: dict,
    current_story_id: str | None, current_attempt: int, event: str,
) -> None:
    """Body of `write_health_snapshot`; caller holds `_HEALTH_LOCK`."""
    try:
        # Load existing to preserve history fields
        existing = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # Count consecutive failures on current story
        consecutive_failures = 0
        if current_story_id and state:
            stories = state.get("stories", {})
            if state.get("specs"):
                # Epic mode — find the right spec's stories
                for sk, sv in state.get("specs", {}).items():
                    if current_story_id in sv.get("stories", {}):
                        stories = sv["stories"]
                        break
            story_state = stories.get(current_story_id, {})
            if story_state.get("status") in ("retrying", "failed"):
                consecutive_failures = story_state.get("attempts", 0)

        child_pids = _get_child_pids()

        snapshot = {
            "heartbeat": now_iso(),
            "orchestrator_pid": os.getpid(),
            "child_pids": child_pids,
            "memory_mb": round(_get_memory_usage_mb(), 1),
            "event": event,
            "current_story_id": current_story_id,
            "current_attempt": current_attempt,
            "consecutive_failures": consecutive_failures,
            "status": state.get("status", "unknown") if state else "unknown",
            "started_at": state.get("started_at", "") if state else "",
            "stories_completed": _count_completed_stories(state),
            "stories_total": _count_total_stories(state),
            "last_control_action": existing.get("last_control_action"),
            "last_control_at": existing.get("last_control_at"),
            # Per-story control history so a split/skip on one story does not
            # permanently suppress healing of later stories (issue #21). Keyed by
            # story_id → {action, at, count}.
            "control_history": existing.get("control_history", {}),
        }

        _atomic_json_write(path, snapshot)
    except OSError as e:
        log(f"  WARNING: Failed to write health snapshot: {e}")


def _touch_heartbeat(config: dict) -> None:
    """Refresh ONLY the ``heartbeat`` field of an existing health snapshot.

    Deliberately never *creates* the file: before the first snapshot there is
    nothing to keep alive (the status skill already handles "no health data
    yet"), and after end-of-run cleanup re-creating it would re-dirty the
    worktree. Best-effort — a failed refresh must never affect execution.
    """
    path = get_health_path(config)
    with _HEALTH_LOCK:
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                health = json.load(f)
            health["heartbeat"] = now_iso()
            _atomic_json_write(path, health)
        except (json.JSONDecodeError, OSError):
            pass


def start_heartbeat_thread(config: dict) -> threading.Event:
    """Start a daemon thread stamping ``heartbeat`` every HEARTBEAT_INTERVAL s.

    Full snapshots are only written at attempt boundaries, but an
    implementation session legitimately runs 25-35 minutes for an L/XL story —
    so a boundary-only heartbeat routinely exceeded the 20-minute staleness
    threshold `/kit-tools:execution-status` documents, and the field cried wolf
    on every healthy long story. A timer refresh makes the name accurate:
    heartbeat now means "the orchestrator *process* is alive", independent of
    how long the current session runs — which finally makes a genuinely wedged
    orchestrator inside a long attempt detectable.

    Returns a stop Event (set it to end the loop). The thread is a daemon, so
    a crash/exit that never sets it cannot keep the process alive.
    """
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(HEARTBEAT_INTERVAL):
            _touch_heartbeat(config)

    threading.Thread(target=_beat, name="kit-heartbeat", daemon=True).start()
    return stop


def _count_completed_stories(state: dict | None) -> int:
    """Count completed stories across single or epic mode state."""
    if not state:
        return 0
    count = 0
    if state.get("specs"):
        for sv in state["specs"].values():
            for s in sv.get("stories", {}).values():
                if s.get("status") == "completed":
                    count += 1
    else:
        for s in state.get("stories", {}).values():
            if s.get("status") == "completed":
                count += 1
    return count


def _count_total_stories(state: dict | None) -> int:
    """Count total stories tracked in state (not necessarily all stories in spec)."""
    if not state:
        return 0
    count = 0
    if state.get("specs"):
        for sv in state["specs"].values():
            count += len(sv.get("stories", {}))
    else:
        count = len(state.get("stories", {}))
    return count


def read_control_file(config: dict) -> dict | None:
    """Read and consume the supervisor control file.

    Returns the control action dict if present, or None.
    The control file is deleted after reading to prevent re-processing.
    """
    path = get_control_path(config)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            control = json.load(f)
        # Consume: delete the file so we don't re-process
        os.remove(path)
        log(f"  Supervisor control action received: {control.get('action', 'unknown')}")

        # Record in health snapshot (lock: the heartbeat thread also
        # read-modify-writes this file)
        health_path = get_health_path(config)
        with _HEALTH_LOCK:
            if os.path.exists(health_path):
                try:
                    with open(health_path, "r") as f:
                        health = json.load(f)
                    health["last_control_action"] = control.get("action")
                    health["last_control_at"] = now_iso()
                    # Also record per-story so the supervisor's "already
                    # intervened?" check is scoped to the story it acted on,
                    # not the whole epic (issue #21).
                    _sid = control.get("story_id")
                    if _sid:
                        _hist = health.setdefault("control_history", {})
                        _entry = _hist.setdefault(_sid, {"count": 0})
                        _entry["action"] = control.get("action")
                        _entry["at"] = now_iso()
                        _entry["count"] = _entry.get("count", 0) + 1
                    _atomic_json_write(health_path, health)
                except (json.JSONDecodeError, OSError):
                    pass

        return control
    except (json.JSONDecodeError, OSError) as e:
        log(f"  WARNING: Failed to read control file: {e}")
        # Delete malformed file to prevent repeated errors
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def handle_control_action(
    control: dict, config: dict, state: dict, spec_path: str,
    feature_name: str, spec_key: str | None = None
) -> str:
    """Execute a supervisor control action.

    Returns an action result string:
      - "continue" — resume normal execution
      - "pause" — pause execution and wait for user input
      - "stories_updated" — stories were split/modified, restart story loop
      - "abort" — stop execution entirely
    """
    action = control.get("action", "")
    # Operator/supervisor forced past normal flow — the Spec-Kitty force-override
    # analog. One event covers every branch (pause/skip/split/abort); the reducer
    # counts these so an experiment can tell autonomous success from a human
    # rescue.
    log_event(
        config, "supervisor.action",
        actor={"kind": "human", "id": "supervisor"},
        spec=spec_key, story=control.get("story_id"),
        action=action, reason=control.get("reason"),
    )

    if action == "pause":
        reason = control.get("reason", "Supervisor requested pause")
        log(f"  Supervisor pause: {reason}")
        state["status"] = "paused"
        save_state(state, config)
        write_notification(
            config, "supervisor_pause",
            "Supervisor paused execution",
            reason,
            severity="warning",
        )
        # Create pause file so the orchestrator's existing pause logic kicks in
        pause_path = os.path.join(config["project_dir"], "kit_tools", ".pause_execution")
        try:
            with open(pause_path, "w") as f:
                f.write(f"Supervisor pause: {reason}\n")
        except OSError:
            pass
        return "pause"

    elif action == "split_story":
        return _handle_split_story(control, config, state, spec_path, feature_name, spec_key)

    elif action == "skip_story":
        story_id = control.get("story_id", "")
        reason = control.get("reason", "Supervisor skipped")
        log(f"  Supervisor skip: {story_id} — {reason}")
        update_state_story(
            state, story_id, "failed", 0,
            learnings=[f"Skipped by supervisor: {reason}"],
            failure=f"Skipped: {reason}",
            spec_key=spec_key, failure_type="SUPERVISOR_SKIP"
        )
        save_state(state, config)
        write_notification(
            config, "supervisor_skip",
            f"Supervisor skipped {story_id}",
            reason,
            severity="info",
        )
        return "stories_updated"

    elif action == "abort":
        reason = control.get("reason", "Supervisor aborted execution")
        log(f"  Supervisor abort: {reason}")
        state["status"] = "failed"
        save_state(state, config)
        write_notification(
            config, "supervisor_abort",
            "Supervisor aborted execution",
            reason,
            severity="critical",
        )
        return "abort"

    else:
        log(f"  WARNING: Unknown control action: {action}")
        return "continue"


def _handle_split_story(
    control: dict, config: dict, state: dict, spec_path: str,
    feature_name: str, spec_key: str | None = None
) -> str:
    """Handle a split_story control action from the supervisor.

    The supervisor provides the full split: new story definitions with IDs,
    titles, descriptions, and acceptance criteria. The orchestrator applies
    the split to the feature spec and updates execution state.

    Expected control format:
    {
        "action": "split_story",
        "story_id": "US-003",
        "reason": "Story too large, timed out 3x",
        "new_stories": [
            {
                "id": "US-010",
                "title": "First half of original US-003",
                "description": "...",
                "criteria": ["- [ ] Criterion 1", "- [ ] Criterion 2"],
                "hints": "Implementation hints (optional)"
            },
            {
                "id": "US-011",
                "title": "Second half of original US-003",
                "description": "...",
                "criteria": ["- [ ] Criterion 3", "- [ ] Criterion 4"],
                "hints": "Implementation hints (optional)"
            }
        ]
    }
    """
    story_id = control.get("story_id", "")
    new_stories = control.get("new_stories", [])
    reason = control.get("reason", "Supervisor split")

    if not story_id or not new_stories:
        log(f"  WARNING: split_story missing story_id or new_stories")
        return "continue"

    # Validate new story IDs are major numbers (US-NNN), not sub-letters
    for ns in new_stories:
        ns_id = ns.get("id", "")
        if not re.match(r"^US-\d{3,}$", ns_id):
            log(f"  WARNING: Invalid story ID format '{ns_id}' — must be US-NNN (major numbers only)")
            return "continue"

    log(f"  Splitting {story_id} into {len(new_stories)} stories: {[s['id'] for s in new_stories]}")

    # --- Update the feature spec file ---
    if not spec_path or not os.path.exists(spec_path):
        log(f"  WARNING: Cannot split — spec file not found: {spec_path}")
        return "continue"

    try:
        with open(spec_path, "r") as f:
            spec_content = f.read()

        # Find the original story section (### US-XXX: Title)
        story_pattern = re.compile(
            rf"(### {re.escape(story_id)}:.*?)(?=\n### US-|\n## |\Z)",
            re.DOTALL
        )
        match = story_pattern.search(spec_content)
        if not match:
            log(f"  WARNING: Could not find {story_id} section in spec file")
            return "continue"

        # Build replacement text: mark original as split, add new stories
        replacement = f"### {story_id}: [SPLIT — see {', '.join(s['id'] for s in new_stories)}]\n\n"
        replacement += f"> Split by supervisor: {reason}\n\n"

        for ns in new_stories:
            replacement += f"### {ns['id']}: {ns['title']}\n\n"
            if ns.get("description"):
                replacement += f"{ns['description']}\n\n"
            replacement += "**Acceptance Criteria:**\n"
            for criterion in ns.get("criteria", []):
                if not criterion.startswith("- ["):
                    criterion = f"- [ ] {criterion}"
                replacement += f"{criterion}\n"
            if ns.get("hints"):
                replacement += f"\n**Implementation Hints:**\n{ns['hints']}\n"
            replacement += "\n"

        spec_content = spec_content[:match.start()] + replacement + spec_content[match.end():]

        with open(spec_path, "w") as f:
            f.write(spec_content)

        log(f"  Updated spec file: {spec_path}")

    except OSError as e:
        log(f"  WARNING: Failed to update spec file for split: {e}")
        return "continue"

    # --- Update execution state ---
    # Mark original story as split (not failed, not completed)
    update_state_story(
        state, story_id, "failed", 0,
        learnings=[f"Split into {[s['id'] for s in new_stories]}: {reason}"],
        failure=f"Split by supervisor",
        spec_key=spec_key, failure_type="SUPERVISOR_SPLIT"
    )

    save_state(state, config)

    # Commit the spec change. warn-only: the on-disk spec is the source of
    # truth mid-run, and if the commit fails the dirty spec makes the next
    # attempt-branch checkout raise loudly (GitCommandError) at the point
    # where it actually blocks progress.
    project_dir = config["project_dir"]
    run_git(["add", spec_path], project_dir, warn=True)
    run_git(
        ["commit", "-m", f"chore({feature_name}): split {story_id} into {', '.join(s['id'] for s in new_stories)}"],
        project_dir, warn=True
    )

    write_notification(
        config, "supervisor_split",
        f"Story {story_id} split",
        f"Split into {', '.join(s['id'] for s in new_stories)}: {reason}",
        severity="info",
    )

    log(f"  Split complete. New stories will be picked up in next iteration.")
    return "stories_updated"


def check_orchestrator_duration(state: dict) -> bool:
    """Check if the orchestrator has exceeded its max duration. Returns True if expired.

    Measures from ``run_started_at`` — stamped fresh on every orchestrator
    (re)launch — rather than ``started_at``, which records when the epic *first*
    began. Reading ``started_at`` here meant resuming a run that began >24h ago
    instantly re-tripped this net before doing any work. Falls back to
    ``started_at`` for state written before ``run_started_at`` existed.
    """
    started = state.get("run_started_at") or state.get("started_at") or ""
    if not started:
        return False
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
        if elapsed > MAX_ORCHESTRATOR_DURATION:
            log(f"  Safety net: orchestrator running for {elapsed/3600:.1f}h — exceeds 24h limit")
            return True
    except (ValueError, TypeError):
        pass
    return False


def pause_file_exists(project_dir: str) -> bool:
    """Check for kit_tools/.pause_execution file."""
    return os.path.exists(os.path.join(project_dir, "kit_tools", ".pause_execution"))


def _healing_control_action(project_dir: str) -> str | None:
    """Return a queued supervisor action that should self-clear a pause, if one
    exists.

    ``split_story`` and ``skip_story`` are the supervisor's *autonomous healing*
    actions — a guarded retry-pause is kept alive specifically so the supervisor
    can issue them. But control actions are otherwise only consumed *between
    attempts*, and a guarded pause has no more attempts, so a queued heal would
    sit forever (issue #19). A queued ``pause`` is the opposite — a deliberate
    escalation to a human — and must never self-clear.
    """
    path = os.path.join(project_dir, CONTROL_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            action = (json.load(f) or {}).get("action")
    except (OSError, ValueError):
        return None
    return action if action in ("split_story", "skip_story") else None


def wait_for_pause_removal(project_dir: str, config: dict | None = None) -> None:
    """Poll until the pause file is removed, with timeout."""
    log("Paused. Remove kit_tools/.pause_execution to resume.")
    elapsed = 0
    last_reminder = 0
    while pause_file_exists(project_dir):
        # A guarded retry-pause is kept alive so the supervisor can heal it. If
        # it has queued a split/skip, clear the pause ourselves so the executor
        # consumes the action on resume — otherwise the heal is never applied
        # and the run stalls until the 24h timeout (issue #19).
        healing = _healing_control_action(project_dir)
        if healing:
            log(f"  Supervisor queued '{healing}' — clearing the guarded pause and "
                f"resuming so the action is consumed.")
            try:
                os.remove(os.path.join(project_dir, "kit_tools", ".pause_execution"))
            except OSError:
                pass
            break
        time.sleep(PAUSE_POLL_INTERVAL)
        elapsed += PAUSE_POLL_INTERVAL
        if elapsed - last_reminder >= PAUSE_LOG_INTERVAL:
            log(f"  Still paused ({elapsed}s elapsed). Remove kit_tools/.pause_execution to resume.")
            last_reminder = elapsed
        if elapsed >= PAUSE_MAX_WAIT:
            log(f"  WARNING: Pause timeout reached ({PAUSE_MAX_WAIT}s). Auto-resuming.")
            if config:
                write_notification(
                    config, "pause_timeout",
                    "Pause timeout reached",
                    f"Auto-resumed after {PAUSE_MAX_WAIT}s pause.",
                    severity="warning",
                )
            pause_path = os.path.join(project_dir, "kit_tools", ".pause_execution")
            try:
                os.remove(pause_path)
            except OSError:
                pass
            break
    log("Pause file removed. Resuming execution.")


