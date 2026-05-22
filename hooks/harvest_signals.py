#!/usr/bin/env python3
"""
harvest_signals.py - Capture skill telemetry from KitTools artifacts.

Trigger: Stop
Writes signals to $PLUGIN_ROOT/.feedback/signals.jsonl for retrospective analysis.
Silent no-op if no kit_tools/ directory exists in the project.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def resolve_plugin_root():
    """Derive plugin root from this script's own location."""
    return Path(__file__).resolve().parent.parent


def detect_skill(kit_dir: Path) -> tuple[str | None, dict]:
    """Detect which skill ran based on artifact presence. Returns (skill_name, raw_data)."""

    exec_state = kit_dir / "specs" / ".execution-state.json"
    exec_config = kit_dir / "specs" / ".execution-config.json"
    exec_log = kit_dir / "EXECUTION_LOG.md"

    if exec_state.exists():
        try:
            state = json.loads(exec_state.read_text())
            config = {}
            if exec_config.exists():
                config = json.loads(exec_config.read_text())
            return "execute-epic", {"state": state, "config": config, "log_path": exec_log}
        except (json.JSONDecodeError, OSError):
            pass

    validate_summary = kit_dir / ".validate_epic_summary.json"
    if validate_summary.exists():
        try:
            summary = json.loads(validate_summary.read_text())
            return "validate-epic", {"summary": summary, "summary_path": validate_summary}
        except (json.JSONDecodeError, OSError):
            pass

    validate_files = list(kit_dir.glob(".validate_epic_*.json"))
    if validate_files:
        results = []
        for f in sorted(validate_files):
            try:
                results.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        if results:
            return "validate-epic", {"results": results}

    return None, {}


def extract_execute_signal(data: dict, project_name: str) -> dict:
    """Extract signal from execute-epic artifacts."""
    state = data.get("state", {})
    config = data.get("config", {})
    log_path = data.get("log_path")

    is_epic = "epic" in state
    mode = state.get("mode", config.get("mode", "unknown"))

    if is_epic:
        specs = state.get("specs", {})
        specs_completed = sum(1 for s in specs.values() if s.get("status") == "completed")
        specs_failed = sum(1 for s in specs.values() if s.get("status") == "failed")
        specs_total = len(specs)

        stories_completed = 0
        stories_failed = 0
        total_retries = 0
        failure_patterns = []

        for spec_name, spec_data in specs.items():
            for story_id, story_data in spec_data.get("stories", {}).items():
                attempts = story_data.get("attempts", 0)
                status = story_data.get("status", "unknown")
                if status in ("passed", "completed"):
                    stories_completed += 1
                elif status == "failed":
                    stories_failed += 1
                if attempts > 1:
                    total_retries += attempts - 1
                    if attempts >= 3:
                        failure_patterns.append({
                            "story": story_id,
                            "spec": spec_name,
                            "attempts": attempts,
                            "status": status,
                        })
    else:
        specs_total = 1
        specs_completed = 1 if state.get("status") == "completed" else 0
        specs_failed = 1 if state.get("status") == "failed" else 0
        stories = state.get("stories", {})
        stories_completed = sum(1 for s in stories.values() if s.get("status") in ("passed", "completed"))
        stories_failed = sum(1 for s in stories.values() if s.get("status") == "failed")
        total_retries = sum(max(0, s.get("attempts", 1) - 1) for s in stories.values())
        failure_patterns = [
            {"story": sid, "attempts": s.get("attempts", 0), "status": s.get("status", "unknown")}
            for sid, s in stories.items()
            if s.get("attempts", 0) >= 3
        ]

    duration_hours = None
    started = state.get("started_at")
    updated = state.get("updated_at")
    if started and updated:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            duration_hours = round((end_dt - start_dt).total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            pass

    log_patterns = extract_log_patterns(log_path) if log_path else {}

    signal = {
        "skill": "execute-epic",
        "project": project_name,
        "mode": mode,
        "outcome": state.get("status", "unknown"),
        "is_epic": is_epic,
        "metrics": {
            "specs_total": specs_total,
            "specs_completed": specs_completed,
            "specs_failed": specs_failed,
            "stories_completed": stories_completed,
            "stories_failed": stories_failed,
            "total_retries": total_retries,
            "sessions": state.get("sessions", {}),
        },
        "duration_hours": duration_hours,
    }

    if failure_patterns:
        signal["failure_patterns"] = failure_patterns
    if log_patterns:
        signal["log_patterns"] = log_patterns

    return signal


def extract_log_patterns(log_path: Path) -> dict:
    """Scan EXECUTION_LOG.md for recurring patterns worth capturing."""
    if not log_path or not log_path.exists():
        return {}

    try:
        content = log_path.read_text()
    except OSError:
        return {}

    patterns = {}

    fail_matches = re.findall(r"(?:FAIL|FAILED|failed verification)", content)
    if len(fail_matches) > 0:
        patterns["total_failures_logged"] = len(fail_matches)

    retry_matches = re.findall(r"[Rr]etry|[Aa]ttempt (\d+)", content)
    if retry_matches:
        patterns["retry_mentions"] = len(retry_matches)

    pause_matches = re.findall(r"[Pp]aus(?:e|ed|ing)", content)
    if pause_matches:
        patterns["pause_mentions"] = len(pause_matches)

    return patterns


def extract_validate_signal(data: dict, project_name: str) -> dict:
    """Extract signal from validate-epic artifacts."""
    summary = data.get("summary")
    summary_path = data.get("summary_path")

    if summary:
        signal = {
            "skill": "validate-epic",
            "project": project_name,
            "outcome": summary.get("overall_readiness", "unknown"),
            "metrics": {
                "epic_name": summary.get("epic_name"),
                "specs_reviewed": summary.get("specs_reviewed", 0),
                "reviewer_verdicts": summary.get("reviewer_verdicts", {}),
                "findings": summary.get("finding_counts", {}),
            },
        }
        if summary_path:
            try:
                Path(summary_path).unlink()
            except OSError:
                pass
        return signal

    results = data.get("results", [])

    verdicts = {}
    finding_counts = {"critical": 0, "warning": 0, "info": 0}

    for result in results:
        review_type = result.get("review_type", "unknown")
        verdict = result.get("overall_verdict", "unknown")
        verdicts[review_type] = verdict

        for finding in result.get("findings", []):
            severity = finding.get("severity", "info")
            if severity in finding_counts:
                finding_counts[severity] += 1

    overall = "ready"
    if finding_counts["critical"] > 0:
        overall = "not-ready"
    elif finding_counts["warning"] > 0:
        overall = "needs-work"

    return {
        "skill": "validate-epic",
        "project": project_name,
        "outcome": overall,
        "metrics": {
            "reviewers_run": len(results),
            "verdicts": verdicts,
            "findings": finding_counts,
        },
    }


def write_signal(plugin_root: Path, signal: dict):
    """Append a signal line to the feedback JSONL file."""
    feedback_dir = plugin_root / ".feedback"
    feedback_dir.mkdir(exist_ok=True)

    signal["timestamp"] = datetime.now(timezone.utc).isoformat()

    signals_file = feedback_dir / "signals.jsonl"
    with open(signals_file, "a") as f:
        f.write(json.dumps(signal, separators=(",", ":")) + "\n")


def main():
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    kit_dir = Path(project_dir) / "kit_tools"
    if not kit_dir.is_dir():
        return

    plugin_root = resolve_plugin_root()
    project_name = Path(project_dir).name

    skill, data = detect_skill(kit_dir)
    if not skill:
        return

    if skill == "execute-epic":
        signal = extract_execute_signal(data, project_name)
    elif skill == "validate-epic":
        signal = extract_validate_signal(data, project_name)
    else:
        return

    signal["project_dir"] = project_dir
    write_signal(plugin_root, signal)


if __name__ == "__main__":
    main()
