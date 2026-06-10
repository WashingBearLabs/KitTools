---
name: doctor
description: Check plugin self-integrity and environment health — broken references, agent token drift, stale installs, missing tools
---

# Doctor

Hey Claude! Let's give the KitTools installation a health check. This verifies the plugin is internally consistent (skills reference agents/scripts that exist, agent token contracts match, hooks compile, the orchestrator runs) and that this machine can actually execute it — before a broken piece surfaces mid-epic.

All findings are **advisory** — nothing here blocks a workflow.

## Step 1: Run the diagnostic script

Run the doctor with the project directory so project-level checks are included:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/doctor.py" --project "$(pwd)"
```

**If `$CLAUDE_PLUGIN_ROOT` is unset or the script is missing there** (a stale root from before a `/plugin update`), resolve the active install first: read `~/.claude/plugins/installed_plugins.json`, find the `kit-tools@washingbearlabs` entry, and use its `installPath` value as the plugin root.

The script exits `0` (healthy), `1` (warnings), or `2` (errors). Add `--json` if you need machine-readable output instead.

## Step 2: Present the results

Show the script's output to the user. Then, for anything that isn't a ✓, add a short plain-language explanation of the *consequence* — what would have broken, and when. For example:

| Finding type | What it means for the user |
|---|---|
| `skills` broken reference | The named skill would fail mid-run when it tries to read that agent/script |
| `agent-tokens` drift | An agent would receive a literal `{{TOKEN}}` in its prompt (or a skill builds context nothing reads) |
| `hooks` missing/broken | That automation (scratchpad, timestamps, notifications) silently stops happening |
| `orchestrator` errors | Autonomous execution would crash at launch or mid-epic |
| `environment` tmux missing | Autonomous/guarded execution can't launch (supervised mode still works) |
| `install` stale root / version behind | The session may be running old plugin code; recent fixes aren't active |
| `project` worktree.yaml / gitignore issues | Worktree provisioning produces a non-runnable tree, or `git add -A` scoops registry state |

## Step 3: Offer fixes

For findings that have a `fix:` line, offer to apply it (with the user's confirmation for anything that mutates state — e.g. running `ensure-gitignore`, re-running `/kit-tools:init-project`). For environment gaps (tmux, gh, PyYAML), give the install command for the user's platform and let them run it.

If everything is healthy, say so briefly and stop — no ceremony needed.

## When to suggest this skill

- After `/plugin update` (catches stale `$CLAUDE_PLUGIN_ROOT` and half-updated installs)
- When a skill fails with a missing-file or literal-`{{TOKEN}}` symptom
- Before launching a long autonomous execution on a new machine or project
