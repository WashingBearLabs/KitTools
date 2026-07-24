# Configure Models — Reference

Canonical schema, role map, and selection flow for kit-tools model preferences.
This file is the single source of truth: the `configure-models` skill drives the
interactive flow from here, and the review/validation skills reference this file
for their lazy first-run prompt.

---

## The file

**Path:** `kit_tools/model_preferences.json` (committed — shared across the team).

**Schema:**

```json
{
  "version": 1,
  "models": {
    "implementer": "sonnet",
    "verifier": "opus",
    "validator": "opus",
    "reviewer": "opus",
    "second_opinion": "sonnet",
    "escalation": { "to": "opus", "on_attempt": 2, "sizes": ["L", "XL"] }
  }
}
```

- `version` — schema version (currently `1`).
- `models` — role → model. Every value is a model the local `claude` CLI
  accepts: an alias (`sonnet`, `opus`, `haiku`) or a full model id
  (e.g. `claude-sonnet-4-6`).
- A role may be **omitted**; an omitted or empty-string role falls back to its
  built-in default (see the role table). Partial files are fine — you only need
  to list the roles you're changing.
- `escalation` is a policy object, not a flat model name: `to` is the model to
  escalate to, `on_attempt` is the retry attempt that triggers it, and `sizes`
  are the story sizes it applies to. A bare string is also accepted and treated
  as `{ "to": "<string>", "on_attempt": 2, "sizes": ["L", "XL"] }`.

---

## Roles and which skills use them

| Role | Used by | Built-in default | What it drives |
|------|---------|------------------|----------------|
| `implementer` | `execute-epic` (orchestrator) | `sonnet` | Generates the code for each story — the bulk of the work. |
| `verifier` | `execute-epic` (orchestrator) | `opus` | Independent review of each story's diff. |
| `validator` | `execute-epic` (orchestrator) | `opus` | The session that runs `validate-implementation` after stories pass. |
| `escalation` | `execute-epic` (orchestrator) | `opus` | Model to retry large stories with on a later attempt. |
| `reviewer` | `validate-epic`, `validate-implementation`, `sync-project` | session model | The review-panel agents (spec completionist / story quality / salty engineer / codebase fit / security; impl quality / security / compliance; drift detection). |
| `second_opinion` | `validate-epic` | the *other* of sonnet/opus | The deliberately contrasting reviewer — see below. |

> The orchestrator only consumes `implementer`, `verifier`, `validator`, and
> `escalation`; the review skills consume `reviewer` and `second_opinion`.
> Keeping them in one file means one place to look, even though no single skill
> uses every role.

### The `second_opinion` role is special

Its whole value is running on a **different model** than the other reviewers —
different training surfaces different blind spots. So:

- If unset, it means **"use the other model from the reviewers."** If the
  reviewers run on Opus, use Sonnet; if they run on Sonnet, use Opus. If the
  reviewer model can't be determined, default to `opus`.
- If pinned, choose a model **different** from the `reviewer` role. Pinning it to
  the same model as the reviewers defeats the purpose — warn the user if they do.

---

## Selection menu (canonical)

Present these four options whenever selecting models (both the `configure-models`
skill and the review skills' lazy first-run use this exact menu):

```
How should kit-tools choose models?
  A. Defaults  — Sonnet for implementation, Opus for verification/validation/review
                 (recommended); the second opinion runs on the other model
  B. All Opus  — every role on Opus (highest cost, highest quality)
  C. All Sonnet— every role on Sonnet (lowest cost, suitable for low-risk work)
  D. Custom    — set each role individually
```

Mapping each choice to the `models` block:

- **A. Defaults** — `implementer` = `sonnet`; `verifier`, `validator`,
  `reviewer`, `escalation.to` = `opus`; `second_opinion` = `sonnet`. (Or omit
  everything — the built-in defaults are identical.)
- **B. All Opus** — every role `opus`; keep `second_opinion` = `sonnet` so it
  still contrasts.
- **C. All Sonnet** — every role `sonnet`; keep `second_opinion` = `opus` so it
  still contrasts.
- **D. Custom** — prompt for each role in the table above (offer the built-in
  default for each).

Valid values: aliases `sonnet` / `opus` / `haiku`, or full ids like
`claude-sonnet-4-6`.

---

## Lazy first-run contract (for the review/validation skills)

`validate-epic`, `validate-implementation`, and `sync-project` should, at the
point where they first dispatch model-bearing agents:

1. Read `kit_tools/model_preferences.json`.
2. **If it exists**, resolve each role they need from the `models` block
   (missing → use the built-in default / session model; a concrete value → pass
   it as the Task tool's `model` parameter). Run silently — do **not** prompt.
3. **If it does not exist**, present the Selection menu **once**, write the file
   per the schema above, then proceed with the chosen values. Do not prompt again
   on subsequent runs.

To change models later, the user runs `/kit-tools:configure-models` (or edits the
JSON directly).

---

## How roles become a model at dispatch time

- **Task-tool agents** (review panels, second opinion): pass the resolved role
  value as the Task tool's `model` parameter. If a `reviewer` value is unset,
  omit the parameter (the agent runs on the session model).
- **Orchestrator sessions** (`execute-epic`): the Python orchestrator reads this
  file itself via `get_model_config()` in `scripts/orchestrator/config.py`,
  layering it beneath any per-run `.execution-config.json` override, then passes
  the result to `claude --model`.

---

## Portability note

This schema is intentionally build-agnostic: the **structure** (roles, layering,
selection menu) is identical across the Claude Code and GitHub Copilot CLI builds
of kit-tools. Only the **model-id values** differ between builds (each build uses
the model names its own CLI accepts — Claude aliases here, versioned Copilot ids
in the Copilot build). Keep the schema and role names in sync when porting
between builds; localize only the example values.
