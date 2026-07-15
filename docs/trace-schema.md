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

## Public data contract for consumers

`~/.kit/feedback/<project-id>/` is not internal KitTools state — it's a **stable interface** a
separate application (e.g. a companion research/benchmarking app) depends on, reading across
every repo that runs KitTools autonomously. Treat it accordingly:

- The **directory layout** (`runs/<run_id>.json`, `signals.jsonl`) and the **record schema**
  documented in this file are the contract. The compatibility rule below (readers ignore unknown
  fields; additions are non-breaking; removals/renames bump `SIGNAL_SCHEMA_VERSION`) applies to
  this directory exactly as it applies to the event stream.
- **Two record kinds** share this directory, distinguished by the `skill` field:
  `"execute-epic"` (single-spec or epic execution) and `"validate-epic"` (spec-quality review).
  Their `run_id`s follow different conventions: execute-epic uses `run-<compact-utc>-<8hex>`
  (minted once by `new_run_id()`); validate-epic uses a **stable per-epic**
  `validate-<epic-slug>`, so re-validating the same epic upserts one record (latest pass wins)
  instead of accumulating. A consumer keying off `run_id` shape should expect both forms.
- The canonical **join key** across the two record kinds is `(project, epic, spec)` — see "The
  keystone join" below.
- `origin` (top-level, every record) and per-spec `result_commit`
  (`metrics.per_spec[<spec>].result_commit`, execute-epic records only) are the **provenance** a
  consumer uses to check out and evaluate the code a run actually produced — `origin` identifies
  the repo, `result_commit` identifies the commit on the feature branch.
- This directory is **read-only** from a consumer's perspective. `trace_reduce.py` is the single
  writer; nothing outside KitTools should write into `~/.kit/feedback/`.
- **Known limitation:** there is currently no way to recover the *resolved* model identifier (a
  versioned model string distinct from an alias like `"sonnet"`) from a session — the `claude`
  CLI's `--output-format json` envelope doesn't expose one. `session.metrics.model` and
  `actor.model` are always the alias/override string from `model_config`, never a resolved id.
  "Hold the model fixed" across weeks currently means holding the *alias* fixed — a weaker
  guarantee than pinning an exact model build — worth knowing before comparing runs weeks apart.

**Who reduces, and when.** The reduction logic lives in
`scripts/orchestrator/trace_reduce.py`. Two callers share it:
- the `harvest_signals` **Stop hook** — fires per session, for mid-run snapshots
  and for non-orchestrator skills (validate-epic);
- the **orchestrator itself** — calls `finalize_run_trace(config, state)` at
  end-of-run, with the live in-memory state, *before* artifact cleanup. This is
  essential: a run's terminal status (`completed`/`failed`) is set in Python
  after the last child session stops, so no Stop hook ever fires with it. The
  hook alone would record `running`/`paused` forever and never the outcome.

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

The envelope mirrors the **Spec Kitty** event shape so the two systems' traces
stay structurally comparable for head-to-head evaluation. The one mapping a
shared consumer must apply: our discriminator is **`event_type`**; Spec Kitty's
is **`event_name`** (`event_id` / `at` / `actor` / run-vs-mission identity /
payload line up directly).

## Event taxonomy

Run lifecycle (`entry.py`):

- `run.started` — `{mode, branch, max_retries, is_rerun, epic, spec_count?, config_snapshot, config_fingerprint, experiment_id, arm, kit_tools_version, origin}` — `config_snapshot` records the scaffold "knobs" the run executed with (`{models, completion_strategy, worktree_mode, epic_pause_between_specs, mode, max_retries, session_ready_gate}`) so an ablation can attribute an outcome change to the knob that changed. `config_fingerprint` is `sha256(canonical_json(knobs))[:16]` (canonical = `sort_keys=True, separators=(",", ":")`) computed over `config_snapshot` **minus** `session_ready_gate` — that field is a one-off per-run human decision (did the operator proceed past a not-ready spec), not a reusable scaffold knob, so it's deliberately excluded from the hash: two runs with an otherwise-identical scaffold must fingerprint identically regardless of that call. (`session_ready_gate` still appears on `config_snapshot` itself — only excluded from the hash.) The fingerprint is deterministic, so a consumer can recompute it the same way to verify, or use it directly to group runs with an identical scaffold even when `experiment_id`/`arm` weren't set. `experiment_id`/`arm` are free-form strings set externally by a research harness — `null` on a normal run, never invented. `kit_tools_version` is the plugin version that produced this run (behavior changes release to release — see `docs/experiments/README.md`); resolved from the running code's own file location, not `$CLAUDE_PLUGIN_ROOT`, since that env var can go stale within a long-lived session after `/plugin update`. `origin` is the normalised git remote URL (same normalisation as `<project-id>`; `null` if the repo has no `origin`) — captured once at run start and copied verbatim onto the record by the reducer (deterministic); a live fallback lookup at reduction time only applies to record kinds with no `run.started` event (validate-epic, legacy pre-2.7.0 runs).

  **Known limitation, multi-spec epics:** `session_ready_gate` reflects a single pre-flight check made once at epic launch, but an epic run (`epic=True`) can execute many feature specs in sequence, each with its own `session_ready` frontmatter value. The recorded gate is accurate for the spec checked at launch, not necessarily every spec the run goes on to execute — treat it as an approximate, not per-spec, signal for epic runs.
- `run.completed` — `{outcome, duration_seconds, sessions, specs_total?}`
- `recovery.succeeded` — `{recovered_from, attempt}` — run recovered from a git-stuck state (e.g. merge-conflict abort) and continued.
- `supervisor.action` — `{action, reason, story?}` (actor `human`) — operator/supervisor forced past normal flow (pause/skip/split/abort): the Spec-Kitty force-override analog.
- `orchestrator_crashed`, `abort_*` — error/crash path (pre-existing)

Per-story (`executor.py`):

- `story.implement.started` — `{attempt, spec_size}` (actor carries the model)
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
- `merge.landed` — `{target_branch, verified, via?, status?, commit?}` — `commit` is the
  feature-branch HEAD SHA immediately after a per-story attempt merge lands (emitted from
  `executor.py`); best-effort, `null` on any git failure. **Not** populated on the final
  feature→main merge's worktree/server-side path (`git_ops.py`'s `gh pr merge` — the local
  worktree's HEAD never advances there, so there's no local SHA to read). Note the SHA is logged
  on the event immediately, but `metrics.per_spec[<spec>].result_commit` (below) — the reliable
  per-spec provenance to use — is only persisted to state once the cross-story regression check
  that runs right after confirms the merge is durable; a merge that trips the regression gate is
  `git revert`ed and never becomes that spec's `result_commit`, so the field never points at
  known-bad or since-undone code.
- `merge.failed` — `{target_branch, reason, via?}`
- `merge.deferred` — `{target_branch, status, via}` (pushed/PR-open but not merged)
- `merge.blocked` — `{target_branch, reason}` (e.g. validation not clean)

Spec quality (`validate-epic`, via `scripts/emit_validate_events.py`):

- `spec.validate.scored` — one per reviewer per spec: `{reviewer, canonical_verdict, readiness_score, finding_counts, spec_finding_counts?, panel_tier?, panel_reviewers?}`. `finding_counts` is the **epic** total; `spec_finding_counts` (optional) is the accurate **per-spec** breakdown — use it for per-spec analysis rather than the epic total. `panel_tier` (`"full"` or `"quick"`) and `panel_reviewers` (the actual reviewer-id list run) record which panel composition validated this epic — epic-wide context carried on every event, `null` on a pre-2.9.0 event. `validate-epic` runs in the interactive session, not the orchestrator, so it bridges into the same stream through the emitter script. Its run is keyed by a **stable per-epic** `run_id` (`validate-<epic-slug>`), so re-validating an epic upserts one record (latest pass wins) instead of accumulating.

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
  "epic": "my-epic",
  "outcome": "completed",
  "metrics": { "specs_completed": 3, "stories_completed": 12, "total_retries": 4,
               "per_spec": { "feature-a.md": {"status": "completed", "stories_completed": 4,
                                              "stories_failed": 0, "retries": 1,
                                              "result_commit": "a1b2c3d4e5f6..."} }, ... },
  "detectors": { "rejection_cycles": 2, "friction": 1, "retries": 4, "escalations": 1,
                 "supervisor_actions": 0, "recoveries": 1, "merges_landed": 3,
                 "merges_failed": 0, "completions": 12, "crashes": 0 },
  "tokens": { "estimate": {"input": N, "output": N},
              "measured": {"input": N, "output": N, "cost_usd": N, "measured_calls": N} },
  "functional_pass_proxy": true,
  "eval": { "functional_pass": null, "intent_alignment_score": null, "spec_quality": null },
  "experiment_id": null,
  "arm": null,
  "config_snapshot": { "models": {"implementer": "sonnet", "verifier": "opus", "validator": "opus",
                                   "escalation": {"to": "opus", "on_attempt": 2, "sizes": ["L", "XL"]}},
                        "completion_strategy": "pr", "worktree_mode": true,
                        "epic_pause_between_specs": false, "mode": "autonomous",
                        "max_retries": 5,
                        "session_ready_gate": {"spec_ready": true, "proceeded_despite_false": false} },
  "config_fingerprint": "3f9a1c2b7e4d5f60",
  "kit_tools_version": "2.8.5",
  "started_at": "2026-06-23T10:00:00+00:00",
  "completed_at": "2026-06-23T11:30:00+00:00",
  "origin": "github.com/org/myrepo",
  "last_reduced_at": "2026-06-23T..."
}
```

`validate-epic` records additionally carry `panel_tier`/`panel_reviewers` (top-level, alongside
`eval.spec_quality`) instead of `metrics.per_spec[...].result_commit` — a validation run has no
code to attribute a commit to.

The record schema is versioned independently (`SIGNAL_SCHEMA_VERSION`, currently
`"2"`; `"1"` was the flat pre-2.7.0 line). `last_reduced_at` is the reduction
wall-clock — explicitly **not** part of the deterministic reduction (it's the one
field that varies between two reductions of the same stream); named so consumers
don't mistake it for a run timestamp.

**`functional_pass_proxy`** is a provisional run-level signal derived from
verifier verdicts (`completed` with no failed stories → `true`; `failed`/
`crashed` → `false`; else `null`). It is deliberately **separate** from the
eval-layer `eval.functional_pass` slot — the proxy gives a usable dependent
variable on day one without pretending to be a real test/judge signal.

### The keystone join

The keystone question — does pre-execution spec quality predict downstream
output quality? — joins a **validate-epic** record (carrying the per-reviewer
`readiness_score` vector + per-spec verdicts) to the **execute-epic** record for
the same spec. The two runs have independent `run_id`s, so the canonical join key
is **`(project, epic, spec)`**: both record kinds now carry `epic` at top level,
the validate record holds per-spec scores, and the execute record holds
`metrics.per_spec[<spec>]` outcomes. (A future enhancement may also stamp the
validate `run_id` onto the execute run for a direct link.) Once joined, `origin`
(top-level, both record kinds) plus the execute record's
`metrics.per_spec[<spec>].result_commit` are what a downstream evaluation layer
uses to actually check out and grade the code that spec produced.

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
