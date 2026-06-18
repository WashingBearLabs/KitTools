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
import sys

# Reuse the orchestrator's event primitive so the envelope (schema_version,
# event_id, at, run, actor, payload) stays identical to executor-emitted events.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from orchestrator.events import log_event, new_run_id
except Exception as e:  # pragma: no cover - import-environment guard
    print(f"emit_validate_events: could not import orchestrator.events ({e}); skipping")
    sys.exit(0)


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
    # finding_counts in the summary is epic-level (one block), not per-spec —
    # attach it to each event as context rather than inventing per-spec splits.
    finding_counts = summary.get("finding_counts", {})

    # Each validation pass is its own run; a fresh id lets the reducer treat a
    # re-validation after fixes as a distinct, idempotent record.
    config = {
        "project_dir": project_dir,
        "feature_name": epic_name,
        "run_id": new_run_id(),
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
                finding_counts=finding_counts,
            )
            emitted += 1

    print(f"emit_validate_events: emitted {emitted} spec.validate.scored event(s) for {epic_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
