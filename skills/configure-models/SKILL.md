---
name: configure-models
description: View or change which Claude models kit-tools uses for each role (implementation, verification, review, second opinion). Persists your choices to a committed kit_tools/model_preferences.json so every skill and the autonomous orchestrator read the same defaults. Invoke to set up model preferences, change them, or inspect the current configuration.
---

# Configure Models

kit-tools runs work through several **roles** — implementing stories, verifying
diffs, running review panels, and giving a second opinion from a different model.
Each role has a built-in default (Sonnet for implementation, Opus for the
quality-critical roles), but you can pin a specific model to any role. This skill
lets you **view or change** those choices and saves them to a single
project-level file that every other skill reads.

> **One source of truth.** The preferences live in
> `kit_tools/model_preferences.json` (committed, so the whole team shares them).
> `/kit-tools:validate-epic`, `/kit-tools:validate-implementation`,
> `/kit-tools:sync-project`, and the `/kit-tools:execute-epic` orchestrator all
> resolve their model choices from this file. See `REFERENCE.md` in this skill
> directory for the full schema, the role → skill map, and the canonical
> selection menu.

## When to use this skill

- **First-time setup** — establish which models each role should use.
- **Change models** — switch a role to a different model, or back to the default.
- **Inspect** — just show the current configuration and where it's read.

The review/validation skills also invoke this flow **lazily**: the first time you
run one of them without a preferences file, they present the same menu once,
persist your choice, then run silently afterward. Running this skill directly is
how you change that choice later.

---

## Step 1: Read the current preferences

Look for `kit_tools/model_preferences.json` in the project root.

- **If it exists:** parse the `models` block and show the user the current value
  for each role in a short table (role, model, which skills use it — see the
  role map in `REFERENCE.md`). Ask whether they want to change anything.
- **If it does not exist:** tell the user no preferences are set yet (every role
  uses its built-in default — Sonnet for implementation, Opus for
  verification/validation/review) and offer to configure them now.

If the project has no `kit_tools/` directory at all, tell the user to run
`/kit-tools:init-project` first — preferences are stored under `kit_tools/`.

---

## Step 2: Offer the selection menu

Present the canonical menu from `REFERENCE.md` ("Selection menu"):

```
How should kit-tools choose models?
  A. Defaults  — Sonnet for implementation, Opus for verification/validation/review
                 (recommended); the second opinion runs on the other model
  B. All Opus  — every role on Opus (highest cost, highest quality)
  C. All Sonnet— every role on Sonnet (lowest cost, suitable for low-risk work)
  D. Custom    — set each role individually
```

- For **A**, you may write the defaults explicitly or leave roles unset (unset
  roles fall back to the built-in Sonnet/Opus split).
- For **B**/**C**, set every role to `opus` / `sonnet` respectively; keep
  `second_opinion` on the *other* model so it still contrasts (see below).
- For **D**, walk each role listed in `REFERENCE.md` and ask for a model
  (`sonnet`, `opus`, `haiku`, or a full `claude-*` id).

**Second opinion:** its value comes from running on a *different* model than the
reviewers — different training surfaces different blind spots. If the reviewers
are on Opus, keep `second_opinion` on Sonnet (and vice-versa). Explain this if
the user tries to set it to the same model as the reviewers.

Validate every value against what the local `claude` CLI accepts — aliases
`sonnet` / `opus` / `haiku` or full model ids like `claude-sonnet-4-6`.

---

## Step 3: Write the file

Write `kit_tools/model_preferences.json` using the schema in `REFERENCE.md`
(`version` + a `models` object). Preserve any roles the user didn't change. Only
include roles that exist in the schema; a role left at its built-in default may
be written explicitly or omitted (omitted roles fall back to the default).

Example (defaults, written explicitly):

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

Then confirm what was written and remind the user it's committed (shared with the
team) and read by every model-dispatching skill. Because the file is
version-controlled, suggest they commit it with their next change.

---

## Step 4: Confirm and exit

Show the final configuration and stop. No ceremony — the next
`/kit-tools:validate-epic`, `/kit-tools:validate-implementation`,
`/kit-tools:sync-project`, or `/kit-tools:execute-epic` run will use these values
automatically.
