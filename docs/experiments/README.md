# Experiment baselines

`baseline.config.json` is the canonical scaffold knob-set the ablation program varies *from*,
one knob at a time. `execute_epic_config_snapshot` mirrors the **exact** shape a real record's
`config_snapshot` field has (see `../trace-schema.md`) — same keys (`models`, not
`model_config`; flat, not nested under `execute_epic`) — so it can be canonical-JSON-hashed the
same way `config_fingerprint` is and compared directly against a real run's fingerprint.
`validate_epic` (tier + reviewer list) lives on a separate record kind and isn't part of that
hash; it's included here for reference only.

**`session_ready_gate` is deliberately absent from `execute_epic_config_snapshot`.** It's a
per-run observed fact (did this specific spec's readiness check pass, did an operator override
it), not a scaffold knob to pin a baseline value for — and `config_fingerprint` itself excludes
it from the hash for the same reason (see `_FINGERPRINT_EXCLUDED_KEYS` in `entry.py`). A real
record's `config_snapshot` will still carry it; just don't expect it here.

**Pinned at KitTools v2.8.5.** Behavior tied to skill prose (planning rigor, story-sizing
guidance, implementation-hint richness — the knobs that aren't config; see the knob inventory in
`../trace-schema.md`) changes release to release even when no config value does — e.g.
permissive decomposition landed in 2.8.3, shift-left planning in 2.7.0. A run's
`kit_tools_version` field says which plugin version actually produced it; if that doesn't match
this file's `pinned_at_kit_tools_version`, the run isn't a valid baseline/treatment comparison
until this file is re-pinned (regenerate it against the new version's defaults and bump the pin).

**An experiment overrides exactly one knob from this baseline** — e.g. a treatment arm named
`escalation-threshold` might set `model_config.escalation.on_attempt` to `3` while leaving
everything else here untouched. Set `experiment_id` and `arm` in `.execution-config.json` so the
resulting run's record can be grouped and compared (see the "Public data contract" section of
`../trace-schema.md`); to verify a run's actual scaffold matched the intended arm even when
`experiment_id` wasn't set, hash `execute_epic_config_snapshot` the same way
(`json.dumps(sort_keys=True, separators=(",", ":"))` → `sha256` → first 16 hex chars) and compare
against the record's `config_fingerprint`.

This file is a reference artifact only — nothing in the orchestrator reads it at runtime.
