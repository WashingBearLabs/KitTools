"""Per-run trace reducer — the shared core behind both the Stop-hook
(`hooks/harvest_signals.py`) and the orchestrator's own end-of-run finalize.

Why this is a package module, not just the hook: the Stop hook fires per
session, but a run's TERMINAL status (completed/failed) is set in Python AFTER
the last `claude -p` child session stops — so a hook-only design captures
`running`/`paused` forever and never the outcome that matters. The orchestrator
therefore calls `finalize_run_trace(config, state)` itself at end-of-run (with
the live in-memory state, before artifact cleanup), guaranteeing a terminal
record. The Stop hook still runs for mid-run snapshots and for skills that
aren't the orchestrator (validate-epic).

Everything here is a deterministic, idempotent reduction of the append-only
event stream + the state snapshot into one record per run, upserted by run_id.
See docs/trace-schema.md.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .registry import derive_project_id

FEEDBACK_HOME = Path("~/.kit/feedback").expanduser()

# Per-run record schema. Bump on a breaking change; additions are non-breaking
# because every reader ignores unknown fields. v1 was the flat pre-2.7.0 line.
SIGNAL_SCHEMA_VERSION = "2"

# Event-type prefixes used to tell an execute run from a validate run even when
# events lack a run_id (legacy in-dir streams that mixed both).
_EXECUTE_PREFIXES = ("run.", "story.", "merge.", "retry.", "model.", "regression.",
                     "session.", "recovery.", "supervisor.", "orchestrator_", "abort_")
_VALIDATE_PREFIXES = ("spec.validate.",)


# --- Event-stream reading ----------------------------------------------------


def read_events(kit_dir: Path) -> list[dict]:
    """Parse the append-only event stream. Tolerant: skips unparseable lines so
    one corrupt line can't sink the whole reduction."""
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


def _run_kind(event_type: str) -> str | None:
    if event_type.startswith(_VALIDATE_PREFIXES):
        return "validate-epic"
    if event_type.startswith(_EXECUTE_PREFIXES):
        return "execute-epic"
    return None


def group_events_by_run(events: list[dict]) -> dict[str, list[dict]]:
    """Bucket events by run_id. Events lacking a run_id are split by kind into
    `_norun:execute` / `_norun:validate` so a legacy mixed stream doesn't let
    validate events shadow the execute reduction (T4-O)."""
    groups: dict[str, list[dict]] = {}
    for e in events:
        rid = (e.get("run") or {}).get("run_id")
        if not rid:
            kind = _run_kind(e.get("event_type", "")) or "unknown"
            rid = f"_norun:{kind}"
        groups.setdefault(rid, []).append(e)
    return groups


def classify_run(events: list[dict]) -> str | None:
    """Decide which skill a run's events came from (run_id-bucketed events are
    homogeneous; this also covers the _norun split)."""
    types = {e.get("event_type", "") for e in events}
    if any(t.startswith(_VALIDATE_PREFIXES) for t in types):
        return "validate-epic"
    if any(t.startswith(_EXECUTE_PREFIXES) for t in types):
        return "execute-epic"
    return None


# --- Detectors ---------------------------------------------------------------


def compute_detectors(events: list[dict]) -> dict:
    """Deterministic reliability detectors over one run's event list.

    rejection_cycles = verifications that sent work back WITH feedback (the
    productive kind). friction = backward movement WITHOUT actionable feedback.
    supervisor_actions = operator/supervisor forced past a gate (Spec Kitty's
    force-override analog). recoveries = git-stuck states the run recovered from.
    """
    d = {
        "rejection_cycles": 0, "friction": 0, "retries": 0, "escalations": 0,
        "crashes": 0, "recoveries": 0, "supervisor_actions": 0,
        "merges_attempted": 0, "merges_landed": 0, "merges_failed": 0,
        "completions": 0,
    }
    for e in events:
        et = e.get("event_type", "")
        p = e.get("payload", {}) or {}
        if et == "story.verify.rejected":
            d["rejection_cycles" if p.get("has_feedback") else "friction"] += 1
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
        elif et == "supervisor.action":
            d["supervisor_actions"] += 1
        elif et == "merge.attempted":
            d["merges_attempted"] += 1
        elif et == "merge.landed":
            d["merges_landed"] += 1
        elif et == "merge.failed":
            d["merges_failed"] += 1
        elif et == "story.completed":
            d["completions"] += 1
    return d


# --- State-snapshot rollup ---------------------------------------------------


def _empty_eval_slots() -> dict:
    """Slots a later eval layer fills, joined by run_id. Null = not yet
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
    """Roll up per-spec / per-story state into completion + retry counts, plus a
    per-spec breakdown (spec name → status/counts) so spec quality can be joined
    to that spec's execution outcome (the keystone join, T1-D)."""
    is_epic = "epic" in state
    per_spec: dict[str, dict] = {}
    if is_epic:
        specs = state.get("specs", {})
        specs_completed = sum(1 for s in specs.values() if s.get("status") == "completed")
        specs_failed = sum(1 for s in specs.values() if s.get("status") == "failed")
        specs_total = len(specs)
        stories_completed = stories_failed = total_retries = 0
        for spec_name, spec_data in specs.items():
            sc = sf = rt = 0
            for story_data in spec_data.get("stories", {}).values():
                attempts = story_data.get("attempts", 0)
                status = story_data.get("status", "unknown")
                if status in ("passed", "completed"):
                    sc += 1
                elif status == "failed":
                    sf += 1
                if attempts > 1:
                    rt += attempts - 1
            per_spec[spec_name] = {"status": spec_data.get("status", "unknown"),
                                   "stories_completed": sc, "stories_failed": sf,
                                   "retries": rt}
            stories_completed += sc
            stories_failed += sf
            total_retries += rt
    else:
        specs_total = 1
        specs_completed = 1 if state.get("status") == "completed" else 0
        specs_failed = 1 if state.get("status") == "failed" else 0
        stories = state.get("stories", {})
        stories_completed = sum(1 for s in stories.values() if s.get("status") in ("passed", "completed"))
        stories_failed = sum(1 for s in stories.values() if s.get("status") == "failed")
        total_retries = sum(max(0, s.get("attempts", 1) - 1) for s in stories.values())
        spec_name = state.get("spec", "spec")
        per_spec[spec_name] = {"status": state.get("status", "unknown"),
                               "stories_completed": stories_completed,
                               "stories_failed": stories_failed, "retries": total_retries}

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
        "per_spec": per_spec,
    }


def _tokens_block(state: dict | None) -> dict:
    """Estimate vs measured tokens, kept honestly separate. `measured` is None
    when no session reported real usage."""
    state = state or {}
    est = state.get("token_estimates") or {}
    return {
        "estimate": {"input": est.get("input", 0), "output": est.get("output", 0)},
        "measured": state.get("token_usage"),  # {input, output, cost_usd, ...} or None
    }


def _functional_pass_proxy(outcome: str, metrics: dict) -> bool | None:
    """Provisional run-level functional signal from verifier verdicts — NOT the
    eval layer's `functional_pass` (which stays null until a real test/judge
    signal exists). Labelled distinctly so the two are never confused."""
    if outcome == "completed":
        return metrics.get("stories_failed", 0) == 0
    if outcome in ("failed", "crashed"):
        return False
    return None


def _epic_name(state: dict | None, events: list[dict]) -> str | None:
    if state is not None:
        name = state.get("epic") or state.get("feature") or state.get("spec")
        if name:
            return name
    for e in events:
        feat = (e.get("run") or {}).get("feature")
        if feat:
            return feat
    return None


# --- Per-run reductions ------------------------------------------------------


def reduce_execute_run(
    run_id: str, events: list[dict], state: dict | None, project_name: str,
) -> dict:
    detectors = compute_detectors(events)
    # Use the state snapshot only if it belongs to THIS run (so a stale file
    # from another run can't mislabel the reduction).
    st = state if (state is not None and state.get("run_id") == run_id) else None
    # Terminal outcome: prefer authoritative state.status when state is this run;
    # else the run.completed event; else unknown.
    outcome = "unknown"
    if st is not None:
        outcome = st.get("status", "unknown")
    else:
        for e in events:
            if e.get("event_type") == "run.completed":
                outcome = (e.get("payload") or {}).get("outcome", "completed")

    if st is not None:
        metrics = extract_execute_metrics(st)
    else:
        metrics = {
            "stories_completed": detectors["completions"],
            "total_retries": detectors["retries"],
        }

    return {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "run_id": None if run_id.startswith("_norun") else run_id,
        "skill": "execute-epic",
        "project": project_name,
        "epic": _epic_name(st, events),
        "outcome": outcome,
        "metrics": metrics,
        "detectors": detectors,
        "tokens": _tokens_block(st),
        "functional_pass_proxy": _functional_pass_proxy(outcome, metrics),
        "eval": _empty_eval_slots(),
    }


def reduce_validate_run(run_id: str, events: list[dict], project_name: str) -> dict:
    """Reduce spec.validate.scored events into per-spec reviewer verdicts +
    readiness vector. Vector preserved (never averaged); gate signal is the
    worst score; the vector seeds the eval layer's spec_quality."""
    verdicts: dict[str, dict] = {}
    scores: dict[str, dict] = {}
    finding_counts: dict = {}
    per_spec_findings: dict[str, dict] = {}
    epic = None
    for e in events:
        if e.get("event_type") != "spec.validate.scored":
            continue
        p = e.get("payload") or {}
        run = e.get("run") or {}
        epic = epic or run.get("feature")
        spec = run.get("spec") or p.get("spec") or "unknown"
        reviewer = p.get("reviewer", "unknown")
        verdicts.setdefault(spec, {})[reviewer] = p.get("canonical_verdict")
        if p.get("readiness_score") is not None:
            scores.setdefault(spec, {})[reviewer] = p.get("readiness_score")
        # Per-spec finding_counts when present; falls back to epic-level.
        if p.get("spec_finding_counts"):
            per_spec_findings[spec] = p["spec_finding_counts"]
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
        "run_id": None if run_id.startswith("_norun") else run_id,
        "skill": "validate-epic",
        "project": project_name,
        "epic": epic,
        "outcome": overall,
        "metrics": {
            "reviewer_verdicts": verdicts,
            "reviewer_scores": scores,   # per-reviewer vector, never averaged
            "worst_readiness": worst,
            "finding_counts": finding_counts,
            "per_spec_finding_counts": per_spec_findings or None,
        },
        "eval": {**_empty_eval_slots(), "spec_quality": scores or None},
    }


# --- Legacy fallbacks (no event stream) --------------------------------------


def reduce_legacy_execute(state: dict, project_name: str) -> dict:
    """State-only reduction for pre-2.7.0 runs with no event stream."""
    outcome = state.get("status", "unknown")
    metrics = extract_execute_metrics(state)
    return {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "run_id": state.get("run_id"),
        "skill": "execute-epic",
        "project": project_name,
        "epic": _epic_name(state, []),
        "outcome": outcome,
        "metrics": metrics,
        "detectors": None,  # not derivable without events
        "tokens": _tokens_block(state),
        "functional_pass_proxy": _functional_pass_proxy(outcome, metrics),
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
        "epic": summary.get("epic_name"),
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


# --- Build + idempotent write ------------------------------------------------


def build_records(kit_dir: Path, project_name: str, state: dict | None = None) -> list[dict]:
    """Reduce everything present in a project's kit_tools/ into per-run records.

    `state` may be passed in (the orchestrator's live in-memory state at
    finalize time) so the reduction doesn't depend on the state file still
    existing on disk — it's about to be cleaned up.
    """
    events = read_events(kit_dir)
    records: list[dict] = []

    if state is None:
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


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def upsert_records(project_dir: str, records: list[dict]) -> None:
    """Write each per-run record idempotently:
    - `runs/<run_id>.json` — authoritative per-run reduction (overwrite).
    - `signals.jsonl` — upsert-by-run_id (replace this run's line, append if
      new) so `/retrospective` keeps a flat readable log without duplicates.
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
        # last_reduced_at is the reduction wall-clock — explicitly NOT part of
        # the deterministic reduction (guardrail 6: same stream+state → same
        # record modulo this stamp). Named so consumers don't mistake it for a
        # run timestamp.
        record["last_reduced_at"] = now
        record["project_dir"] = project_dir
        existing.append(json.dumps(record, separators=(",", ":")))
        if record.get("run_id"):
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", record["run_id"])
            _atomic_write(runs_dir / f"{safe}.json", json.dumps(record, indent=2))

    _atomic_write(signals_file, "\n".join(existing) + "\n")


# --- Orchestrator-facing entrypoint ------------------------------------------


def finalize_run_trace(config: dict, state: dict | None = None) -> None:
    """Guarantee a terminal per-run record at end-of-run. Called by the
    orchestrator AFTER the terminal status is set and BEFORE artifact cleanup,
    with the live in-memory `state` so it captures the real outcome + token
    totals even though the state file is about to be deleted. Best-effort —
    a trace write must never break completion (guardrail 1)."""
    try:
        project_dir = config.get("project_dir")
        if not project_dir:
            return
        kit_dir = Path(project_dir) / "kit_tools"
        project_name = Path(project_dir).name
        records = build_records(kit_dir, project_name, state=state)
        upsert_records(project_dir, records)
    except Exception:
        pass
