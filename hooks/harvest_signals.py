#!/usr/bin/env python3
"""
harvest_signals.py - Reduce a run's trace into a per-run telemetry record.

Trigger: Stop. Reduces the append-only event stream
(`kit_tools/.execution-events.jsonl`) plus the state snapshot into ONE
structured record per run, and upserts it under
`~/.kit/feedback/<project-id>/` so the record survives plugin updates (the
same per-user home the worktree registry uses; before 2.6.5 signals lived in
`$PLUGIN_ROOT/.feedback/` and were lost on every marketplace update).

Design (see docs/trace-schema.md):
- **Reducer, not scraper.** Derives detectors (rejection cycles, friction,
  retries, escalations, crashes, merges-landed, completions) from typed events
  instead of regex-scraping the prose log.
- **Idempotent.** Keyed on `run_id`; running twice on the same run produces the
  same record and upserts rather than appends. A run spans many sessions (the
  Stop hook fires per session), so this reflects the latest authoritative state.
- **Non-destructive.** Never deletes source artifacts.
- **Leaves eval slots.** `functional_pass` / `intent_alignment_score` /
  `spec_quality` are emitted null for a later eval layer to attach to, by run_id.

Silent no-op if no kit_tools/ directory exists in the project.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_HOME = Path("~/.kit/feedback").expanduser()

# Per-run record schema. Bump on a breaking change; additions are non-breaking
# because every reader ignores unknown fields. v1 was the flat pre-2.7.0 line.
SIGNAL_SCHEMA_VERSION = "2"


def resolve_plugin_root():
    """Derive plugin root from this script's own location."""
    return Path(__file__).resolve().parent.parent


def derive_project_id(project_dir: str) -> str:
    """Stable per-project id, matching the worktree registry's derivation.

    Imports ``scripts/orchestrator/registry.py`` by path so the two stay in
    lockstep (basename + 8-hex hash of the normalised origin remote, falling
    back to the absolute path). If the import fails for any reason, falls back
    to the same shape computed from the absolute path alone — stable, just
    not remote-aware.
    """
    registry_path = resolve_plugin_root() / "scripts" / "orchestrator" / "registry.py"
    try:
        spec = importlib.util.spec_from_file_location("_kit_registry", registry_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.derive_project_id(project_dir)
    except Exception:
        pass
    key = os.path.abspath(project_dir)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    basename = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(key)).strip("-") or "project"
    return f"{basename}-{digest}"


def migrate_legacy_signals(plugin_root: Path) -> None:
    """One-time move of pre-2.6.5 signals out of the plugin install dir.

    The old global file mixes projects, so it moves wholesale to
    ``~/.kit/feedback/legacy-signals.jsonl`` (appending if several stale
    install dirs each held one) rather than being split per-project.
    """
    old_file = plugin_root / ".feedback" / "signals.jsonl"
    if not old_file.exists():
        return
    try:
        content = old_file.read_text()
        FEEDBACK_HOME.mkdir(parents=True, exist_ok=True)
        legacy = FEEDBACK_HOME / "legacy-signals.jsonl"
        with open(legacy, "a") as f:
            f.write(content)
        old_file.unlink()
        try:
            old_file.parent.rmdir()  # only removes if now empty
        except OSError:
            pass
    except OSError:
        pass


# --- Event-stream reduction --------------------------------------------------


def read_events(kit_dir: Path) -> list[dict]:
    """Parse the append-only event stream. Tolerant: skips unparseable lines so
    a single corrupt line can't sink the whole reduction."""
    events_path = kit_dir / ".execution-events.jsonl"
    if not events_path.exists():
        return []
    events = []
    try:
        for line in events_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return events


def group_events_by_run(events: list[dict]) -> dict[str, list[dict]]:
    """Bucket events by run_id (events lacking one share the `_norun` bucket)."""
    groups: dict[str, list[dict]] = {}
    for e in events:
        rid = (e.get("run") or {}).get("run_id") or "_norun"
        groups.setdefault(rid, []).append(e)
    return groups


def classify_run(events: list[dict]) -> str | None:
    """Decide which skill a run's events came from."""
    types = {e.get("event_type", "") for e in events}
    if "spec.validate.scored" in types:
        return "validate-epic"
    if any(t.startswith(("run.", "story.", "merge.")) for t in types):
        return "execute-epic"
    return None


def compute_detectors(events: list[dict]) -> dict:
    """Deterministic reliability detectors over one run's event list.

    rejection_cycles = verifications that sent work back *with* feedback (the
    productive kind). friction = backward movement *without* actionable feedback
    (feedback-less rejections, verify infra errors, non-permanent impl errors) —
    the Spec-Kitty distinction that separates "review working" from "thrashing".
    """
    d = {
        "rejection_cycles": 0, "friction": 0, "retries": 0, "escalations": 0,
        "crashes": 0, "recoveries": 0, "merges_attempted": 0,
        "merges_landed": 0, "merges_failed": 0, "completions": 0,
    }
    for e in events:
        et = e.get("event_type", "")
        p = e.get("payload", {}) or {}
        if et == "story.verify.rejected":
            if p.get("has_feedback"):
                d["rejection_cycles"] += 1
            else:
                d["friction"] += 1
        elif et == "story.verify.error":
            d["friction"] += 1
        elif et == "story.implement.failed":
            if not p.get("permanent"):
                d["friction"] += 1
        elif et == "retry.triggered":
            d["retries"] += 1
        elif et == "model.escalated":
            d["escalations"] += 1
        elif et in ("orchestrator_crashed", "crash"):
            d["crashes"] += 1
        elif et.startswith("recovery."):
            d["recoveries"] += 1
        elif et == "merge.attempted":
            d["merges_attempted"] += 1
        elif et == "merge.landed":
            d["merges_landed"] += 1
        elif et == "merge.failed":
            d["merges_failed"] += 1
        elif et == "story.completed":
            d["completions"] += 1
    return d


def _empty_eval_slots() -> dict:
    """Slots a later eval layer fills in, joined by run_id. Null = not yet
    measured (never present an unmeasured run as a passing/zero result)."""
    return {
        "functional_pass": None,
        "intent_alignment_score": None,
        "spec_quality": None,
    }


def _duration_hours_from_state(state: dict) -> float | None:
    started = state.get("started_at")
    updated = state.get("updated_at")
    if not (started and updated):
        return None
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        return round((end_dt - start_dt).total_seconds() / 3600, 2)
    except (ValueError, TypeError):
        return None


def extract_execute_metrics(state: dict) -> dict:
    """Roll up per-spec / per-story state into completion + retry counts.
    Shared by the event path and the legacy state-only fallback."""
    is_epic = "epic" in state
    if is_epic:
        specs = state.get("specs", {})
        specs_completed = sum(1 for s in specs.values() if s.get("status") == "completed")
        specs_failed = sum(1 for s in specs.values() if s.get("status") == "failed")
        specs_total = len(specs)
        stories_completed = stories_failed = total_retries = 0
        for spec_data in specs.values():
            for story_data in spec_data.get("stories", {}).values():
                attempts = story_data.get("attempts", 0)
                status = story_data.get("status", "unknown")
                if status in ("passed", "completed"):
                    stories_completed += 1
                elif status == "failed":
                    stories_failed += 1
                if attempts > 1:
                    total_retries += attempts - 1
    else:
        specs_total = 1
        specs_completed = 1 if state.get("status") == "completed" else 0
        specs_failed = 1 if state.get("status") == "failed" else 0
        stories = state.get("stories", {})
        stories_completed = sum(1 for s in stories.values() if s.get("status") in ("passed", "completed"))
        stories_failed = sum(1 for s in stories.values() if s.get("status") == "failed")
        total_retries = sum(max(0, s.get("attempts", 1) - 1) for s in stories.values())

    return {
        "is_epic": is_epic,
        "specs_total": specs_total,
        "specs_completed": specs_completed,
        "specs_failed": specs_failed,
        "stories_completed": stories_completed,
        "stories_failed": stories_failed,
        "total_retries": total_retries,
        "sessions": state.get("sessions", {}),
        "duration_hours": _duration_hours_from_state(state),
    }


def _tokens_block(state: dict | None) -> dict:
    """Estimate vs measured tokens, kept honestly separate. `measured` is None
    when no session reported real usage (older CLI / parse miss)."""
    state = state or {}
    est = state.get("token_estimates") or {}
    measured = state.get("token_usage")
    return {
        "estimate": {"input": est.get("input", 0), "output": est.get("output", 0)},
        "measured": measured,  # {input, output, cost_usd, measured_calls, ...} or None
    }


def reduce_execute_run(
    run_id: str, events: list[dict], state: dict | None, project_name: str,
) -> dict:
    detectors = compute_detectors(events)
    # Final outcome: prefer the authoritative state.status when state belongs to
    # this run; else the run.completed event; else unknown.
    outcome = "unknown"
    if state is not None and state.get("run_id") == run_id:
        outcome = state.get("status", "unknown")
    else:
        for e in events:
            if e.get("event_type") == "run.completed":
                outcome = (e.get("payload") or {}).get("outcome", "completed")

    state_for_metrics = state if (state is not None and state.get("run_id") == run_id) else None
    if state_for_metrics is not None:
        metrics = extract_execute_metrics(state_for_metrics)
    else:
        # Event-only fallback (state file already cleaned up or from another run)
        metrics = {
            "stories_completed": detectors["completions"],
            "total_retries": detectors["retries"],
        }

    return {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "run_id": run_id if run_id != "_norun" else None,
        "skill": "execute-epic",
        "project": project_name,
        "outcome": outcome,
        "metrics": metrics,
        "detectors": detectors,
        "tokens": _tokens_block(state_for_metrics),
        "eval": _empty_eval_slots(),
    }


def reduce_validate_run(run_id: str, events: list[dict], project_name: str) -> dict:
    """Reduce spec.validate.scored events into per-spec reviewer verdicts +
    readiness vector. The vector is preserved (never averaged); the gate signal
    is the worst score, and the vector seeds the eval layer's spec_quality."""
    verdicts: dict[str, dict] = {}
    scores: dict[str, dict] = {}
    finding_counts: dict = {}
    for e in events:
        if e.get("event_type") != "spec.validate.scored":
            continue
        p = e.get("payload") or {}
        spec = (e.get("run") or {}).get("spec") or p.get("spec") or "unknown"
        reviewer = p.get("reviewer", "unknown")
        verdicts.setdefault(spec, {})[reviewer] = p.get("canonical_verdict")
        if p.get("readiness_score") is not None:
            scores.setdefault(spec, {})[reviewer] = p.get("readiness_score")
        if p.get("finding_counts"):
            finding_counts = p["finding_counts"]

    all_scores = [v for spec_scores in scores.values() for v in spec_scores.values()]
    worst = min(all_scores) if all_scores else None
    overall = "ready"
    if finding_counts.get("critical", 0) > 0:
        overall = "not-ready"
    elif finding_counts.get("warning", 0) > 0:
        overall = "needs-work"

    return {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "run_id": run_id if run_id != "_norun" else None,
        "skill": "validate-epic",
        "project": project_name,
        "outcome": overall,
        "metrics": {
            "reviewer_verdicts": verdicts,
            "reviewer_scores": scores,   # per-reviewer vector, never averaged
            "worst_readiness": worst,
            "finding_counts": finding_counts,
        },
        "eval": {**_empty_eval_slots(), "spec_quality": scores or None},
    }


# --- Legacy fallbacks (no event stream) --------------------------------------


def reduce_legacy_execute(state: dict, project_name: str) -> dict:
    """State-only reduction for pre-2.7.0 runs with no event stream."""
    return {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "run_id": state.get("run_id"),
        "skill": "execute-epic",
        "project": project_name,
        "outcome": state.get("status", "unknown"),
        "metrics": extract_execute_metrics(state),
        "detectors": None,  # not derivable without events
        "tokens": _tokens_block(state),
        "eval": _empty_eval_slots(),
    }


def reduce_legacy_validate(summary: dict, project_name: str) -> dict:
    """Summary-only reduction when the emitter script didn't run (no events)."""
    scores = summary.get("reviewer_scores", {}) or {}
    all_scores = [v for spec_scores in scores.values() for v in spec_scores.values()]
    return {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "run_id": None,
        "skill": "validate-epic",
        "project": project_name,
        "outcome": summary.get("overall_readiness", "unknown"),
        "metrics": {
            "epic_name": summary.get("epic_name"),
            "specs_reviewed": summary.get("specs_reviewed", 0),
            "reviewer_verdicts": summary.get("reviewer_verdicts", {}),
            "reviewer_scores": scores,
            "worst_readiness": min(all_scores) if all_scores else None,
            "finding_counts": summary.get("finding_counts", {}),
        },
        "eval": {**_empty_eval_slots(), "spec_quality": scores or None},
    }


# --- Idempotent writes -------------------------------------------------------


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def upsert_records(project_dir: str, records: list[dict]) -> None:
    """Write each per-run record idempotently:
    - `runs/<run_id>.json` — authoritative per-run reduction (overwrite).
    - `signals.jsonl` — upsert-by-run_id (replace the line for this run, append
      if new) so `/retrospective` keeps a flat readable log without duplicates.
    Records without a run_id (legacy) are appended (can't be keyed).
    """
    if not records:
        return
    feedback_dir = FEEDBACK_HOME / derive_project_id(project_dir)
    runs_dir = feedback_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    signals_file = feedback_dir / "signals.jsonl"
    existing: list[str] = []
    replace_ids = {r["run_id"] for r in records if r.get("run_id")}
    if signals_file.exists():
        for line in signals_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                existing.append(line)  # preserve foreign/legacy lines verbatim
                continue
            if obj.get("run_id") and obj.get("run_id") in replace_ids:
                continue  # drop the prior version of this run
            existing.append(line)

    for record in records:
        record["timestamp"] = now
        record["project_dir"] = project_dir
        existing.append(json.dumps(record, separators=(",", ":")))
        if record.get("run_id"):
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", record["run_id"])
            _atomic_write(runs_dir / f"{safe}.json", json.dumps(record, indent=2))

    _atomic_write(signals_file, "\n".join(existing) + "\n")


# --- Entry -------------------------------------------------------------------


def build_records(kit_dir: Path, project_name: str) -> list[dict]:
    """Reduce everything present in a project's kit_tools/ into per-run records."""
    events = read_events(kit_dir)
    records: list[dict] = []

    # Load the state snapshot once (used to enrich the matching execute run).
    state = None
    exec_state = kit_dir / "specs" / ".execution-state.json"
    if exec_state.exists():
        try:
            state = json.loads(exec_state.read_text())
        except (json.JSONDecodeError, OSError):
            state = None

    if events:
        for run_id, run_events in group_events_by_run(events).items():
            kind = classify_run(run_events)
            if kind == "validate-epic":
                records.append(reduce_validate_run(run_id, run_events, project_name))
            elif kind == "execute-epic":
                records.append(reduce_execute_run(run_id, run_events, state, project_name))
        if records:
            return records

    # --- Legacy fallbacks: no usable event stream ---
    if state is not None:
        records.append(reduce_legacy_execute(state, project_name))
        return records

    validate_summary = kit_dir / ".validate_epic_summary.json"
    if validate_summary.exists():
        try:
            summary = json.loads(validate_summary.read_text())
            records.append(reduce_legacy_validate(summary, project_name))
        except (json.JSONDecodeError, OSError):
            pass
    return records


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

    migrate_legacy_signals(resolve_plugin_root())
    project_name = Path(project_dir).name

    records = build_records(kit_dir, project_name)
    upsert_records(project_dir, records)


if __name__ == "__main__":
    main()
