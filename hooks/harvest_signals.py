#!/usr/bin/env python3
"""
harvest_signals.py — Stop-hook wrapper around the trace reducer.

Trigger: Stop. Reduces a project's append-only event stream + state snapshot
into per-run telemetry records under ~/.kit/feedback/<project-id>/ (idempotent,
non-destructive, keyed by run_id). The reduction logic lives in
`scripts/orchestrator/trace_reduce.py` so the orchestrator can invoke the SAME
reducer itself at end-of-run — the Stop hook never fires after a run's terminal
status is set in Python, so a hook-only design would capture `running`/`paused`
forever and never the outcome (see trace_reduce.finalize_run_trace).

This hook still runs for mid-run snapshots and for non-orchestrator skills
(notably validate-epic, whose Stop is the only trigger). Silent no-op if no
kit_tools/ directory exists.
"""
import json
import os
import sys
from pathlib import Path

# The reducer is a package module (it shares logic with the orchestrator). Add
# scripts/ to the path and import it; degrade to a no-op if unavailable so a
# telemetry import failure never disrupts the host session.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from orchestrator import trace_reduce
except Exception:
    trace_reduce = None


def migrate_legacy_signals(plugin_root: Path) -> None:
    """One-time move of pre-2.6.5 signals out of the plugin install dir.

    The old global file mixes projects, so it moves wholesale to
    ``~/.kit/feedback/legacy-signals.jsonl`` rather than being split per-project.
    """
    old_file = plugin_root / ".feedback" / "signals.jsonl"
    if not old_file.exists():
        return
    try:
        content = old_file.read_text()
        home = trace_reduce.FEEDBACK_HOME
        home.mkdir(parents=True, exist_ok=True)
        legacy = home / "legacy-signals.jsonl"
        with open(legacy, "a") as f:
            f.write(content)
        old_file.unlink()
        try:
            old_file.parent.rmdir()  # only removes if now empty
        except OSError:
            pass
    except OSError:
        pass


def main():
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    if trace_reduce is None:
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return
    kit_dir = Path(project_dir) / "kit_tools"
    if not kit_dir.is_dir():
        return

    try:
        migrate_legacy_signals(Path(__file__).resolve().parent.parent)
        records = trace_reduce.build_records(kit_dir, Path(project_dir).name)
        trace_reduce.upsert_records(project_dir, records)
    except Exception:
        # Best-effort telemetry — never disrupt the host session on Stop.
        pass


if __name__ == "__main__":
    main()
