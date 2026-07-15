#!/usr/bin/env python3
"""Emit `spec.validate.scored` trace events from a validate-epic summary.

`validate-epic` runs in the interactive session, not the orchestrator, so it
can't emit lifecycle events the way the executor does. This bridges that seam:
the skill writes `kit_tools/.validate_epic_summary.json` (per-reviewer verdicts
+ readiness scores + finding counts), then runs this script, which reduces that
summary into one `spec.validate.scored` event per spec per reviewer and appends
them to the same `kit_tools/.execution-events.jsonl` stream the executor and the
reducer use. This is the pre-execution spec-quality signal the benchmark joins
to downstream output quality.

Deterministic (no LLM in the loop) and best-effort: any failure exits 0 with a
note, because a trace write must never break the validation flow.

Usage:
    python3 emit_validate_events.py [--summary PATH] [--project DIR]

Defaults: summary = <project>/kit_tools/.validate_epic_summary.json,
project = $CLAUDE_PROJECT_DIR or cwd.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Reuse the orchestrator's event primitive so the envelope (schema_version,
# event_id, at, run, actor, payload) stays identical to executor-emitted events.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from orchestrator.events import log_event
except Exception as e:  # pragma: no cover - import-environment guard
    print(f"emit_validate_events: could not import orchestrator.events ({e}); skipping")
    sys.exit(0)


def _validate_run_id(epic_name: str) -> str:
    """Stable run_id per epic (NOT per invocation), so re-validating the same
    epic after fixes upserts ONE record (latest pass wins via event order)
    instead of accumulating an unbounded record per re-run (T2-J)."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", epic_name).strip("-").lower() or "epic"
    return f"validate-{slug}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit validate-epic trace events")
    parser.add_argument("--summary", default=None)
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    project_dir = args.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    summary_path = args.summary or os.path.join(
        project_dir, "kit_tools", ".validate_epic_summary.json"
    )

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"emit_validate_events: no usable summary at {summary_path} ({e}); skipping")
        return 0

    epic_name = summary.get("epic_name") or "validate-epic"
    verdicts = summary.get("reviewer_verdicts", {}) or {}
    scores = summary.get("reviewer_scores", {}) or {}
    # `finding_counts` is epic-level (one block) — carried as epic context for
    # the overall verdict. `per_spec_finding_counts` (optional, keyed by spec) is
    # the accurate per-spec breakdown; emitted as `spec_finding_counts` so a
    # per-spec analysis isn't fed the epic total (T3-P).
    finding_counts = summary.get("finding_counts", {})
    per_spec_findings = summary.get("per_spec_finding_counts", {}) or {}
    # Panel composition (Phase 1.6): which tier ran and which reviewers —
    # epic-wide context, carried on every event so the reducer can pick it up
    # without a separate mechanism. None on a pre-2.9.0 summary.
    panel_tier = summary.get("tier")
    panel_reviewers = summary.get("reviewers")

    # Stable per-epic run_id (see _validate_run_id): re-validations upsert one
    # record for the epic, latest pass winning, rather than piling up.
    config = {
        "project_dir": project_dir,
        "feature_name": epic_name,
        "run_id": _validate_run_id(epic_name),
    }

    emitted = 0
    for spec_name, spec_verdicts in verdicts.items():
        spec_scores = scores.get(spec_name, {}) if isinstance(scores, dict) else {}
        for reviewer, verdict in (spec_verdicts or {}).items():
            log_event(
                config, "spec.validate.scored",
                spec=spec_name,
                actor={"kind": "agent", "id": reviewer},
                reviewer=reviewer,
                canonical_verdict=verdict,
                readiness_score=spec_scores.get(reviewer),
                finding_counts=finding_counts,                       # epic-level
                spec_finding_counts=per_spec_findings.get(spec_name),  # per-spec or None
                panel_tier=panel_tier,
                panel_reviewers=panel_reviewers,
            )
            emitted += 1

    print(f"emit_validate_events: emitted {emitted} spec.validate.scored event(s) for {epic_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
