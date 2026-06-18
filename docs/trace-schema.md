# KitTools Trace Schema

KitTools emits a structured, append-only **trace** of every autonomous run. One
event stream per run is the single source of truth: `harvest_signals` reduces it
into per-run metrics, and the same stream is what a benchmarking or
retrospective layer reduces into "what helped / what didn't." This document is
the contract for that trace — its envelope, taxonomy, versioning rules, the
cost/token situation, and the eval slots a later layer fills in.

> Audience: anyone consuming KitTools telemetry (benchmark harness, dashboards,
> retrospective tooling) or extending the orchestrator's emission.

## Two files, two scopes

| File | Where | What |
|------|-------|------|
| `kit_tools/.execution-events.jsonl` | the project (or worktree) being executed | append-only **event stream** — every lifecycle event of a run |
| `~/.kit/feedback/<project-id>/runs/<run_id>.json` | per-user home | authoritative **per-run reduction** (one file per run, overwritten idempotently) |
| `~/.kit/feedback/<project-id>/signals.jsonl` | per-user home | flat upsert-by-`run_id` log of the same reductions (read by `/retrospective`) |

`<project-id>` is `registry.derive_project_id` (`<basename>-<8hex>` of the
normalised origin remote). Living under `~/.kit/` means the data survives plugin
updates (marketplace installs get a fresh install path per version).

## Event envelope

Every line in `.execution-events.jsonl` is one JSON object:

```json
{
  "schema_version": "1",
  "event_id": "2026-06-18T17:22:05.123456+00:00#000042",
  "event_type": "story.verify.rejected",
  "severity": "info",
  "at": "2026-06-18T17:22:05.123456+00:00",
  "timestamp": "2026-06-18T17:22:05.123456+00:00",
  "run": { "run_id": "run-20260618T172110-a4d91506",
           "feature": "auth-epic", "spec": "feature-login.md", "story": "US-003" },
  "actor": { "kind": "agent", "id": "story-verifier", "model": "opus" },
  "payload": { "has_feedback": true, "reason": "criterion 2 unmet", "attempt": 2 }
}
```

| Field | Notes |
|-------|-------|
| `schema_version` | envelope version (see compatibility rule). Currently `"1"`. |
| `event_id` | sortable, unique within a process: `<iso>#<seq>`. Gives the reducer a stable total order. |
| `event_type` | the discriminator (taxonomy below). |
| `severity` | `info` \| `warning` \| `critical`. |
| `at` | ISO-8601 UTC emit time. `timestamp` is a one-version alias of `at` (kept so pre-2.7.0 readers keep working; will be removed at the next major bump). |
| `run` | run identity. `run_id` is minted once at `run.started` and stamped on every event of the run; `feature`/`spec`/`story` scope it. |
| `actor` | optional — who emitted it (`kind`: `agent`\|`runtime`\|`human`, plus `id`, `model`). |
| `payload` | event-specific fields. |

The envelope mirrors the **Spec Kitty** event shape (`event_id` / `event_name` /
`at` / `actor` / mission identity / payload) so the two systems' traces stay
structurally comparable for head-to-head evaluation.

## Event taxonomy

Run lifecycle (`entry.py`):

- `run.started` — `{mode, branch, max_retries, is_rerun, epic, spec_count?}`
- `run.completed` — `{outcome, duration_seconds, sessions, specs_total?}`
- `orchestrator_crashed`, `abort_*` — error/crash path (pre-existing)

Per-story (`executor.py`):

- `story.implement.started` — `{attempt}` (actor carries the model)
- `story.implement.completed` — `{attempt, status, has_result}`
- `story.implement.failed` — `{attempt, failure_type, permanent, reason}`
- `story.verify.passed` — `{attempt, verdict, warnings_count}`
- `story.verify.rejected` — `{attempt, has_feedback, failure_type, reason}` — **`has_feedback`** distinguishes a productive review cycle from thrashing; the reducer's `rejection_cycles` vs `friction` split depends on it.
- `story.verify.error` — `{attempt, failure_type, reason}` (infra failure, not a logical rejection)
- `story.completed` — `{attempt, warnings_count, files_changed_count}`
- `retry.triggered` — `{attempt, max_attempts}`
- `model.escalated` — `{from_model, to_model, reason, spec_size, attempt}`
- `regression.detected` — `{attempt, reason}`
- `session.metrics` — `{phase, model, attempt, tokens_input, tokens_output, cost_usd, token_estimate_input, token_estimate_output}` (see cost section)

Merge (`executor.py` per-story attempt merge; `git_ops.py` final feature merge):

- `merge.attempted` — `{target_branch, attempt_branch?}`
- `merge.landed` — `{target_branch, verified, via?, status?}`
- `merge.failed` — `{target_branch, reason, via?}`
- `merge.deferred` — `{target_branch, status, via}` (pushed/PR-open but not merged)
- `merge.blocked` — `{target_branch, reason}` (e.g. validation not clean)

Spec quality (`validate-epic`, via `scripts/emit_validate_events.py`):

- `spec.validate.scored` — one per reviewer per spec: `{reviewer, canonical_verdict, readiness_score, finding_counts}`. `validate-epic` runs in the interactive session, not the orchestrator, so it bridges into the same stream through that emitter script.

## Compatibility rule

The trace is designed to drift gracefully:

- **Readers ignore unknown fields.** Always. A consumer must never error on a
  field it doesn't recognise.
- **Adding a field or a new `event_type` is non-breaking** — no version bump.
- **Removing or renaming a field, or changing its meaning, is breaking** — bump
  `schema_version` and keep a reader shim for the prior version for one major
  cycle (as `timestamp` currently shims `at`).

`harvest_signals` follows this: it tolerates missing `run_id` (legacy runs),
unparseable lines (skipped, not fatal), and absent payload fields.

## Cost & tokens — what's real, what's estimated

Two figures travel side by side, and they are **never conflated**:

- **`token_estimate_*`** — a `chars // 4` heuristic. Always present. Labelled as
  an estimate everywhere; never called `tokens`.
- **`tokens_input` / `tokens_output` / `cost_usd`** — **real** figures parsed
  from the session's `--output-format json` envelope (`usage` +
  `total_cost_usd`). `tokens_input` includes cache-creation and cache-read
  tokens (the real billed input).

When real usage is unavailable (older CLI, a JSON parse miss), the real fields
are `null` — **not zero**. The per-run record's `tokens.measured` block carries
`measured_calls` / `unmeasured_calls` so a consumer can tell "genuinely $0"
(measured) from "unknown" (unmeasured). Honesty over completeness: an unmeasured
run must never be presented as a free run.

## Per-run record + eval slots

Each run reduces to a record (`runs/<run_id>.json`, mirrored as a `signals.jsonl`
line):

```json
{
  "schema_version": "2",
  "run_id": "run-...",
  "skill": "execute-epic",
  "project": "myrepo",
  "outcome": "completed",
  "metrics": { "specs_completed": 3, "stories_completed": 12, "total_retries": 4, ... },
  "detectors": { "rejection_cycles": 2, "friction": 1, "retries": 4, "escalations": 1,
                 "merges_landed": 3, "merges_failed": 0, "completions": 12, "crashes": 0 },
  "tokens": { "estimate": {"input": N, "output": N},
              "measured": {"input": N, "output": N, "cost_usd": N, "measured_calls": N} },
  "eval": { "functional_pass": null, "intent_alignment_score": null, "spec_quality": null }
}
```

The record schema is versioned independently (`SIGNAL_SCHEMA_VERSION`, currently
`"2"`; `"1"` was the flat pre-2.7.0 line).

**Eval slots** are deliberately `null` and filled by a *later* evaluation layer,
joined by `run_id`:

- `functional_pass` — did the merged result pass its functional/eval tests?
- `intent_alignment_score` — LLM-as-judge alignment of the result against the
  original vision/spec intent.
- `spec_quality` — the per-reviewer `readiness_score` vector from
  `validate-epic` (already populated on `validate-epic` records; null on
  `execute-epic` records until joined). The vector is preserved, **never
  averaged** — the gate reads the worst reviewer, and the spread (e.g. a high
  salty score against a low security score) is itself signal.

The keystone question the trace exists to answer: *does higher pre-execution
spec quality (`spec.validate.scored`) predict higher downstream output quality
(`functional_pass` + `intent_alignment_score`)?* That join — across a validation
run and its later execution run — is what the eval layer computes.

## Idempotency

`harvest_signals` is a Stop hook: it fires once per session, but a run spans many
sessions. It is therefore a **deterministic, idempotent reducer** keyed on
`run_id` — running it repeatedly on the same run produces the same record and
**upserts** (overwrites `runs/<run_id>.json`, replaces the matching
`signals.jsonl` line) rather than appending. It never deletes source artifacts.
