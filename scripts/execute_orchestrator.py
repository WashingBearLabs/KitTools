#!/usr/bin/env python3
"""
KitTools Execute Orchestrator

Spawns independent Claude sessions to implement and verify user stories
from a feature spec. Manages execution state, retries, and logging.

Supports two modes:
- Single mode: executes stories from one feature spec on a feature/[name] branch
- Epic mode: chains multiple feature specs on a shared epic/[name] branch

Launched by the /kit-tools:execute-epic skill for autonomous/guarded modes.

Usage:
    python3 execute_orchestrator.py --config kit_tools/specs/.execution-config.json
"""

import argparse
import atexit
import json
import os
import re
import signal
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
import yaml


# --- Constants ---

SESSION_TIMEOUT = 900  # 15 minutes per claude session
PAUSE_POLL_INTERVAL = 10  # seconds between pause file checks
NETWORK_RETRY_WAIT = 30  # seconds between network retries
NETWORK_MAX_RETRIES = 3
PERMANENT_ERROR_KEYWORDS = ["context", "too long", "token limit", "input.*too.*large", "maximum.*context"]
MAX_PROMPT_CHARS = 480_000
DIFF_CONTENT_MAX = 20_000  # max chars of inline diff for verifier
PAUSE_MAX_WAIT = 86400  # 24 hours max pause
PAUSE_LOG_INTERVAL = 60  # log reminder every minute

# File-based result paths (relative to project_dir)
IMPL_RESULT_FILE = os.path.join("kit_tools", ".story-impl-result.json")
VERIFY_RESULT_FILE = os.path.join("kit_tools", ".story-verify-result.json")
NOTIFICATION_FILE = os.path.join("kit_tools", ".execution-notifications")


# --- Notifications ---

# Severity levels that trigger desktop notifications
DESKTOP_NOTIFY_SEVERITIES = {"critical", "warning"}
# Notification types that always trigger desktop notifications regardless of severity
DESKTOP_NOTIFY_TYPES = {"execution_complete", "execution_crashed", "epic_complete"}


def get_notification_path(config: dict) -> str:
    """Return absolute path to the notification file."""
    return os.path.join(config["project_dir"], NOTIFICATION_FILE)


def send_desktop_notification(title: str, message: str) -> None:
    """Send an OS-level desktop notification. Best-effort — swallows all errors."""
    try:
        system = platform.system()
        if system == "Darwin":
            # macOS: use osascript
            escaped_title = title.replace('"', '\\"')
            escaped_msg = message.replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{escaped_msg}" with title "{escaped_title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        elif system == "Linux":
            # Linux: use notify-send if available
            subprocess.run(
                ["notify-send", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    except Exception:
        pass


def write_notification(
    config: dict, ntype: str, title: str, details: str, severity: str = "info"
) -> None:
    """Append a JSON Lines notification entry and send desktop notification for
    important events. Best-effort — swallows OSError."""
    try:
        path = get_notification_path(config)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entry = {
            "type": ntype,
            "title": title,
            "details": details,
            "severity": severity,
            "feature": config.get("feature_name") or config.get("epic_name", ""),
            "timestamp": now_iso(),
        }
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    # Send desktop notification for important events
    if severity in DESKTOP_NOTIFY_SEVERITIES or ntype in DESKTOP_NOTIFY_TYPES:
        feature = config.get("feature_name") or config.get("epic_name", "")
        desktop_title = f"KitTools — {feature}" if feature else "KitTools"
        send_desktop_notification(desktop_title, details)


def kill_tmux_session(config: dict) -> None:
    """Kill the tmux session used to run this orchestrator. Best-effort."""
    session_name = config.get("tmux_session")
    if not session_name:
        return
    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def register_crash_handler(config: dict) -> None:
    """Register atexit + SIGTERM handlers to detect orchestrator crashes."""
    state_path = get_state_path(config)

    def _on_exit():
        try:
            kill_tmux_session(config)
            if not os.path.exists(state_path):
                return
            with open(state_path, "r") as f:
                state = json.load(f)
            if state.get("status") != "running":
                return
            state["status"] = "crashed"
            state["updated_at"] = now_iso()
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
            feature = config.get("feature_name") or config.get("epic_name", "unknown")
            write_notification(
                config, "execution_crashed",
                "Execution crashed",
                f"Orchestrator exited unexpectedly for {feature}",
                severity="critical",
            )
        except Exception:
            pass

    atexit.register(_on_exit)

    def _on_sigterm(signum, frame):
        _on_exit()
        sys.exit(1)

    signal.signal(signal.SIGTERM, _on_sigterm)


# --- State Management ---


def load_config(config_path: str) -> dict:
    """Read .execution-config.json written by the skill."""
    with open(config_path, "r") as f:
        return json.load(f)


def load_or_create_state(config: dict) -> tuple[dict, bool]:
    """Read or create .execution-state.json for single mode. Returns (state, is_rerun)."""
    state_path = get_state_path(config)
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            state = json.load(f)
        # If resuming a completed/failed run, reset status
        if state.get("status") in ("completed", "failed"):
            state["status"] = "running"
            return state, True
        return state, False

    return {
        "spec": os.path.basename(config["spec_path"]),
        "branch": config["branch_name"],
        "mode": config["mode"],
        "max_retries": config.get("max_retries"),
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "status": "running",
        "stories": {},
        "sessions": {"total": 0, "implementation": 0, "verification": 0, "validation": 0},
    }, False


def load_or_create_epic_state(config: dict) -> tuple[dict, bool]:
    """Read or create .execution-state.json for epic mode. Returns (state, is_rerun)."""
    state_path = get_state_path(config)
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            state = json.load(f)
        if state.get("status") in ("completed", "failed"):
            state["status"] = "running"
            return state, True
        return state, False

    return {
        "epic": config["epic_name"],
        "branch": config["branch_name"],
        "mode": config["mode"],
        "max_retries": config.get("max_retries"),
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "status": "running",
        "current_spec": None,
        "specs": {},
        "sessions": {"total": 0, "implementation": 0, "verification": 0, "validation": 0},
    }, False


def save_state(state: dict, config: dict) -> None:
    """Write .execution-state.json."""
    state["updated_at"] = now_iso()
    state_path = get_state_path(config)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def get_state_path(config: dict) -> str:
    """Return path to .execution-state.json in the project."""
    return os.path.join(config["project_dir"], "kit_tools", "specs", ".execution-state.json")


def update_state_story(
    state: dict, story_id: str, status: str, attempt: int,
    learnings: list | None = None, failure: str | None = None,
    spec_key: str | None = None
) -> None:
    """Update a story's entry in the execution state.

    Args:
        spec_key: If set, update state["specs"][spec_key]["stories"][story_id] (epic mode).
                 If None, update state["stories"][story_id] (single mode).
    """
    if spec_key is not None:
        stories_dict = state["specs"][spec_key].setdefault("stories", {})
    else:
        stories_dict = state.setdefault("stories", {})

    entry = stories_dict.get(story_id, {})
    entry["status"] = status
    entry["attempts"] = attempt

    if status == "completed":
        entry["completed_at"] = now_iso()
    if learnings:
        # Cap per-story learnings to prevent unbounded growth (fix #7)
        existing = entry.setdefault("learnings", [])
        existing.extend(learnings)
        if len(existing) > 20:
            entry["learnings"] = existing[-20:]
    if failure:
        entry["last_failure"] = failure

    stories_dict[story_id] = entry


def _store_attempt_diff(state: dict, story_id: str, diff: str, spec_key: str | None) -> None:
    """Store last_attempt_diff in the correct location (single or epic mode)."""
    if spec_key is not None:
        state["specs"][spec_key].setdefault("stories", {}).setdefault(story_id, {})["last_attempt_diff"] = diff
    else:
        state.setdefault("stories", {}).setdefault(story_id, {})["last_attempt_diff"] = diff


# --- Feature Spec Parsing ---


def parse_spec_frontmatter(spec_path: str) -> dict:
    """Parse YAML frontmatter from a feature spec markdown file using PyYAML."""
    with open(spec_path, "r") as f:
        content = f.read()
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    if not isinstance(frontmatter, dict):
        return {}
    # Normalize values:
    # - Exclude None (callers expect missing keys, not None values)
    # - Convert date objects to ISO strings (PyYAML auto-parses YYYY-MM-DD as datetime.date)
    result = {}
    for k, v in frontmatter.items():
        if v is None:
            continue
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def parse_stories_from_spec(spec_path: str) -> list[dict]:
    """Parse user stories from a feature spec markdown file.

    Returns a list of dicts with keys: id, title, description, criteria, criteria_text
    """
    with open(spec_path, "r") as f:
        content = f.read()

    stories = []
    # Match story headers like: ### US-001: Story Title
    story_pattern = re.compile(
        r"^### (US-\d+):\s*(.+?)$", re.MULTILINE
    )

    matches = list(story_pattern.finditer(content))
    for i, match in enumerate(matches):
        story_id = match.group(1)
        story_title = match.group(2).strip()

        # Extract content between this story header and the next (or next ## section)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            # Find the next ## header (not ###)
            next_section = re.search(r"^## ", content[start:], re.MULTILINE)
            end = start + next_section.start() if next_section else len(content)

        story_content = content[start:end]

        # Extract description
        desc_match = re.search(
            r"\*\*Description:\*\*\s*(.+?)(?=\n\*\*|\n###|\Z)",
            story_content, re.DOTALL
        )
        description = desc_match.group(1).strip() if desc_match else ""

        # Extract implementation hints (between **Implementation Hints:** and **Acceptance Criteria:**)
        hints_match = re.search(
            r"\*\*Implementation Hints:\*\*\s*\n(.+?)(?=\n\*\*Acceptance Criteria:\*\*|\n###|\Z)",
            story_content, re.DOTALL
        )
        hints = hints_match.group(1).strip() if hints_match else ""

        # Extract acceptance criteria
        criteria = []
        criteria_pattern = re.compile(r"^- \[[ x]\] (.+)$", re.MULTILINE)
        for crit_match in criteria_pattern.finditer(story_content):
            criteria.append(crit_match.group(1).strip())

        # Check if all criteria are already completed
        unchecked = re.findall(r"^- \[ \] ", story_content, re.MULTILINE)
        checked = re.findall(r"^- \[x\] ", story_content, re.MULTILINE)

        stories.append({
            "id": story_id,
            "title": story_title,
            "description": description,
            "hints": hints,
            "criteria": criteria,
            "criteria_text": "\n".join(
                f"- [ ] {c}" for c in criteria
            ),
            "completed": len(unchecked) == 0 and len(checked) > 0,
        })

    return stories


def update_spec_checkboxes(spec_path: str, story_id: str) -> bool:
    """Mark acceptance criteria as complete for a story in the feature spec.

    Finds the story section by its header and replaces `- [ ]` with `- [x]`
    within that section only.

    Returns True if any checkboxes were updated.
    """
    with open(spec_path, "r") as f:
        content = f.read()

    # Find the story section: ### {story_id}: ...
    # Section ends at the next ### header or end of file
    pattern = re.compile(
        rf"(### {re.escape(story_id)}:.*?)(?=\n### |\Z)",
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return False

    section = match.group(1)
    updated_section = re.sub(r"^- \[ \] ", "- [x] ", section, flags=re.MULTILINE)
    if updated_section == section:
        return False  # Nothing to update

    content = content[:match.start()] + updated_section + content[match.end():]
    with open(spec_path, "w") as f:
        f.write(content)
    return True


def find_next_uncompleted_story(spec_path: str, stories_state: dict) -> dict | None:
    """Find the first story with uncompleted acceptance criteria.

    Args:
        spec_path: Path to the feature spec file.
        stories_state: Dict with a "stories" key mapping story IDs to their state.
                       For single mode: the top-level state.
                       For epic mode: state["specs"][spec_key].
    """
    stories = parse_stories_from_spec(spec_path)
    for story in stories:
        # Check feature spec checkboxes first (source of truth)
        if story["completed"]:
            continue
        # Cross-reference with state JSON
        story_state = stories_state.get("stories", {}).get(story["id"], {})
        if story_state.get("status") == "completed":
            continue
        return story
    return None


# --- Epic Helpers ---


def check_dependencies_archived(project_dir: str, spec_path: str) -> tuple[bool, list[str]]:
    """Check that all depends_on feature specs are archived. Returns (ok, missing_deps)."""
    fm = parse_spec_frontmatter(spec_path)
    deps = fm.get("depends_on", [])
    if not deps:
        return True, []
    archive_dir = os.path.join(project_dir, "kit_tools", "specs", "archive")
    missing = []
    for dep in deps:
        # Check for feature-{dep}.md or prd-{dep}.md in archive (backwards compat)
        candidates = [f"feature-{dep}.md", f"prd-{dep}.md", f"{dep}.md"]
        found = any(os.path.exists(os.path.join(archive_dir, c)) for c in candidates)
        if not found:
            missing.append(dep)
    return len(missing) == 0, missing


def tag_checkpoint(project_dir: str, epic_name: str, feature_name: str) -> None:
    """Create a git tag marking a feature spec checkpoint within an epic."""
    tag_name = f"{epic_name}/{feature_name}-complete"
    run_git(["tag", tag_name], project_dir, check=True)
    log(f"  Tagged checkpoint: {tag_name}")


def archive_spec(project_dir: str, spec_path: str, feature_name: str) -> None:
    """Update feature spec frontmatter and move to archive directory.

    Safety: writes updated content to the archive destination directly,
    then removes the original. This avoids corrupting the source file
    if the move fails.
    """
    with open(spec_path, "r") as f:
        content = f.read()

    # Update frontmatter in memory (use regex on frontmatter block only)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm_match = re.match(r'^(---\s*\n)(.*?)(---)', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(2)
        fm_text = fm_text.replace("status: active", "status: completed")
        fm_text = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {today}", fm_text)
        if "completed:" not in fm_text:
            fm_text = re.sub(
                r"(updated: \d{4}-\d{2}-\d{2})",
                rf"\1\ncompleted: {today}",
                fm_text
            )
        content = fm_match.group(1) + fm_text + fm_match.group(3) + content[fm_match.end():]

    # Write updated content directly to archive destination
    archive_dir = os.path.join(os.path.dirname(spec_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    dest = os.path.join(archive_dir, os.path.basename(spec_path))
    with open(dest, "w") as f:
        f.write(content)

    # Remove original only after archive write succeeds
    os.remove(spec_path)

    # Stage changes
    rel_dest = os.path.relpath(dest, project_dir)
    rel_src = os.path.relpath(spec_path, project_dir)
    run_git(["add", rel_dest], project_dir, check=True)
    run_git(["rm", "--cached", "-f", rel_src], project_dir, check=True)

    log(f"  Archived: {os.path.basename(spec_path)} -> archive/")


# --- Prompt Size Guard ---


def _trim_section(prompt: str, section_header: str, replacement: str) -> str:
    """Replace a markdown section's body with a shorter replacement.

    Finds a heading matching section_header and replaces content up to the
    next heading at the same or higher level.
    """
    # Determine heading level (count leading #)
    level_match = re.match(r"(#+)", section_header.strip())
    level = len(level_match.group(1)) if level_match else 3
    # Escape the header for regex
    escaped = re.escape(section_header.strip())
    # Match from header to next heading at same-or-higher level (or end)
    pattern = re.compile(
        rf"({escaped}\s*\n)(.*?)(?=\n#{{1,{level}}} |\Z)",
        re.DOTALL
    )
    return pattern.sub(rf"\1{replacement}\n", prompt, count=1)


def check_and_trim_prompt(prompt: str, context_type: str) -> str:
    """Trim oversized prompts to fit within MAX_PROMPT_CHARS.

    Args:
        context_type: "implementation" or "verification" — determines trim order.
    """
    if len(prompt) <= MAX_PROMPT_CHARS:
        return prompt

    if context_type == "implementation":
        trim_order = [
            ("### Prior Learnings", "[Trimmed — prompt too large]"),
            ("### Previous Attempt Diff", "[Trimmed — prompt too large]"),
        ]
    elif context_type == "verification":
        trim_order = [
            ("### Diff Content", "[Trimmed — prompt too large]"),
            ("### Files Changed (from git)", "[Trimmed — prompt too large]"),
            ("### Diff Stat", "[Trimmed — prompt too large]"),
        ]
    else:
        trim_order = []

    for header, replacement in trim_order:
        prompt = _trim_section(prompt, header, replacement)
        if len(prompt) <= MAX_PROMPT_CHARS:
            log(f"  Prompt trimmed (removed {header}) to fit size limit.")
            return prompt

    # Final fallback: hard-truncate
    if len(prompt) > MAX_PROMPT_CHARS:
        log(f"  WARNING: Prompt hard-truncated from {len(prompt)} to {MAX_PROMPT_CHARS} chars.")
        prompt = prompt[:MAX_PROMPT_CHARS] + "\n\n[PROMPT TRUNCATED — size limit reached]"

    return prompt


# --- Prompt Building ---


def strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter from a template string.

    Agent templates have YAML frontmatter (---\\n...\\n---) that is metadata
    for the plugin system. When passing templates to `claude -p`, the leading
    `---` is misinterpreted as a CLI flag. Strip it before building prompts.
    """
    stripped = text.lstrip()
    if stripped.startswith("---"):
        end = stripped.find("---", 3)
        if end != -1:
            return stripped[end + 3:].lstrip("\n")
    return text


def gather_prior_learnings(state: dict, current_story_id: str, spec_key: str | None = None) -> list[str]:
    """Gather learnings from completed stories.

    In epic mode, also gathers learnings from all completed feature specs.
    """
    prior_learnings = []

    if spec_key is not None:
        # Epic mode: gather from ALL feature specs' stories
        for pk, spec_data in state.get("specs", {}).items():
            for sid, sdata in spec_data.get("stories", {}).items():
                if pk == spec_key and sid == current_story_id:
                    continue  # Skip current story
                prior_learnings.extend(sdata.get("learnings", []))
    else:
        # Single mode: gather from state["stories"]
        for sid, sdata in state.get("stories", {}).items():
            if sid != current_story_id:
                prior_learnings.extend(sdata.get("learnings", []))

    # Prune learnings: keep only the most recent
    if len(prior_learnings) > 15:
        prior_learnings = prior_learnings[-15:]

    return prior_learnings


def build_implementation_prompt(
    story: dict, config: dict, state: dict, attempt: int,
    feature_name: str | None = None, spec_path: str | None = None,
    spec_key: str | None = None
) -> str:
    """Interpolate the story-implementer template with context.

    Args:
        feature_name: Override for config["feature_name"] (used in epic mode).
        spec_path: Override for config["spec_path"] (used in epic mode).
        spec_key: If set, look up story state in state["specs"][spec_key] (epic mode).
    """
    template = strip_frontmatter(config["implementer_template"])
    context = config.get("project_context", {})
    feat_name = feature_name or config.get("feature_name", "feature")
    spec = spec_path or config.get("spec_path", "")

    # Gather learnings from previous stories
    prior_learnings = gather_prior_learnings(state, story["id"], spec_key)

    # Build retry context
    retry_context = ""
    if attempt > 1:
        if spec_key is not None:
            stories_dict = state.get("specs", {}).get(spec_key, {}).get("stories", {})
        else:
            stories_dict = state.get("stories", {})
        story_state = stories_dict.get(story["id"], {})
        failure = story_state.get("last_failure", "Unknown failure")
        prev_learnings = story_state.get("learnings", [])
        retry_context = (
            f"This is retry attempt {attempt}.\n\n"
            f"Previous failure:\n{failure}\n\n"
            f"Learnings from previous attempts:\n"
            + "\n".join(f"- {l}" for l in prev_learnings)
        )

    # Build previous attempt diff context
    previous_diff = ""
    if attempt > 1:
        if spec_key is not None:
            stories_dict = state.get("specs", {}).get(spec_key, {}).get("stories", {})
        else:
            stories_dict = state.get("stories", {})
        story_state = stories_dict.get(story["id"], {})
        previous_diff = story_state.get("last_attempt_diff", "")
    previous_diff_text = previous_diff if previous_diff else "No previous attempt."

    # Interpolate template
    prompt = template
    prompt = prompt.replace("{{STORY_ID}}", story["id"])
    prompt = prompt.replace("{{STORY_TITLE}}", story["title"])
    prompt = prompt.replace("{{STORY_DESCRIPTION}}", story["description"])
    prompt = prompt.replace("{{IMPLEMENTATION_HINTS}}", story.get("hints") or "No hints provided — explore the codebase.")
    prompt = prompt.replace("{{ACCEPTANCE_CRITERIA}}", story["criteria_text"])
    prompt = prompt.replace("{{FEATURE}}", feat_name)
    prompt = prompt.replace("{{SPEC_OVERVIEW}}", context.get("spec_overview", "Not available"))
    # Reference-based context: paths instead of content
    prompt = prompt.replace("{{SYNOPSIS_PATH}}", context.get("synopsis", "kit_tools/SYNOPSIS.md"))
    prompt = prompt.replace("{{CODE_ARCH_PATH}}", context.get("code_arch", "kit_tools/arch/CODE_ARCH.md"))
    prompt = prompt.replace("{{CONVENTIONS_PATH}}", context.get("conventions", "kit_tools/docs/CONVENTIONS.md"))
    prompt = prompt.replace("{{GOTCHAS_PATH}}", context.get("gotchas", "kit_tools/docs/GOTCHAS.md"))
    prompt = prompt.replace(
        "{{PRIOR_LEARNINGS}}",
        "\n".join(f"- {l}" for l in prior_learnings) if prior_learnings else "None yet"
    )
    prompt = prompt.replace("{{RETRY_CONTEXT}}", retry_context or "First attempt — no retry context.")
    prompt = prompt.replace("{{PREVIOUS_ATTEMPT_DIFF}}", previous_diff_text)
    # Result file path for the agent to write to
    result_path = os.path.join(config["project_dir"], IMPL_RESULT_FILE)
    prompt = prompt.replace("{{RESULT_FILE_PATH}}", result_path)

    # Add autonomous-mode instructions
    prompt += f"\n\n## Additional Instructions (Autonomous Mode)\n"
    prompt += f"- The feature spec file is at: {spec}\n"
    prompt += f"- Read the feature spec directly for full story context\n"
    prompt += f"- Do NOT modify the feature spec file — checkboxes are updated by the orchestrator after verification\n"
    prompt += f'- Commit with message: feat({feat_name}): {story["id"]} - {story["title"]}\n'

    return prompt


def build_verification_prompt(
    story: dict, config: dict, files_changed_from_git: str,
    diff_stat: str = "", test_command: str | None = None, spec_path: str = "",
    diff_content: str = ""
) -> str:
    """Interpolate the story-verifier template with git-sourced context.

    Args:
        files_changed_from_git: File list from `git diff --name-only`, sourced
            by the orchestrator — NOT from the implementer's output.
        diff_stat: Output of `git diff --stat` for the attempt.
        test_command: Auto-detected test command (fail-fast), or None.
        spec_path: Path to the feature spec file for cross-reference.
        diff_content: Inline diff content (truncated if over DIFF_CONTENT_MAX).
    """
    template = strip_frontmatter(config["verifier_template"])
    context = config.get("project_context", {})

    # Derive targeted test command from changed files
    changed_files = [f.strip() for f in files_changed_from_git.split("\n") if f.strip()]
    targeted_test = detect_related_tests(
        changed_files, config["project_dir"], test_command
    )

    # Build the test command section
    if targeted_test:
        test_section = (
            f"**Targeted tests** (based on changed files):\n"
            f"Run: `{targeted_test}`\n\n"
            f"**Important:** Only run the targeted command above. Do NOT run the full test suite. "
            f"Use quiet flags to suppress PASSED lines, but let failure tracebacks flow in full. "
            f"Pipe through `| head -200` as a safety net for runaway output."
        )
        if test_command:
            test_section += (
                f"\n\nFull suite command (for reference only — do NOT run during story verification): "
                f"`{test_command}`"
            )
    elif test_command:
        test_section = (
            f"Run: `{test_command}`\n\n"
            f"**Important:** Use quiet flags to suppress PASSED lines, but let failure tracebacks flow in full. "
            f"Pipe through `| head -200` as a safety net for runaway output."
        )
    else:
        test_section = "No test command detected — skip test step unless criteria explicitly mention tests."

    prompt = template
    prompt = prompt.replace("{{STORY_ID}}", story["id"])
    prompt = prompt.replace("{{STORY_TITLE}}", story["title"])
    prompt = prompt.replace("{{STORY_DESCRIPTION}}", story.get("description") or "No description available.")
    prompt = prompt.replace("{{IMPLEMENTATION_HINTS}}", story.get("hints") or "No hints provided.")
    prompt = prompt.replace("{{ACCEPTANCE_CRITERIA}}", story["criteria_text"])
    prompt = prompt.replace("{{DIFF_STAT}}", diff_stat or "No diff stat available.")
    prompt = prompt.replace("{{FILES_CHANGED}}", files_changed_from_git or "No files changed detected")
    prompt = prompt.replace("{{DIFF_CONTENT}}", diff_content or "No diff content available.")
    # Reference-based context paths
    prompt = prompt.replace("{{SYNOPSIS_PATH}}", context.get("synopsis", "kit_tools/SYNOPSIS.md"))
    prompt = prompt.replace("{{CODE_ARCH_PATH}}", context.get("code_arch", "kit_tools/arch/CODE_ARCH.md"))
    prompt = prompt.replace("{{CONVENTIONS_PATH}}", context.get("conventions", "kit_tools/docs/CONVENTIONS.md"))
    prompt = prompt.replace("{{GOTCHAS_PATH}}", context.get("gotchas", "kit_tools/docs/GOTCHAS.md"))
    prompt = prompt.replace("{{SPEC_PATH}}", spec_path or "Not available")
    prompt = prompt.replace("{{TEST_COMMAND}}", test_section)
    # Result file path for the agent to write to
    result_path = os.path.join(config["project_dir"], VERIFY_RESULT_FILE)
    prompt = prompt.replace("{{RESULT_FILE_PATH}}", result_path)

    return prompt


# --- Claude Session ---


def _is_permanent_error(stderr_text: str) -> bool:
    """Check if a session error is permanent (not worth retrying)."""
    lower = stderr_text.lower()
    return any(re.search(kw, lower) for kw in PERMANENT_ERROR_KEYWORDS)


def is_session_error(output: str) -> bool:
    """Check if output represents any kind of session error."""
    return output.startswith("SESSION_ERROR:") or output.startswith("SESSION_ERROR_PERMANENT:")


def run_claude_session(prompt: str, project_dir: str) -> str:
    """Execute a claude -p session and capture output.

    Retries up to NETWORK_MAX_RETRIES times for network errors.
    Returns the session stdout on success, or a SESSION_ERROR/SESSION_ERROR_PERMANENT
    string on failure.
    """
    clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            proc = subprocess.Popen(
                ["claude", "-p", prompt, "--dangerously-skip-permissions"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_dir,
                env=clean_env,
                start_new_session=True,
            )

            try:
                stdout, stderr_out = proc.communicate(timeout=SESSION_TIMEOUT)
            except subprocess.TimeoutExpired:
                # Kill the entire process group (claude + all children like pytest, node, etc.)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    proc.kill()
                proc.wait()
                return f"SESSION_ERROR: Timed out after {SESSION_TIMEOUT}s"

            if proc.returncode == 0:
                return stdout

            stderr = stderr_out.strip()
            is_network = any(kw in stderr.lower() for kw in ("network", "connection", "timeout", "econnrefused"))

            # Retry network errors (unless this is the last attempt)
            if is_network and attempt < NETWORK_MAX_RETRIES:
                log(f"  Network error (attempt {attempt}/{NETWORK_MAX_RETRIES}), retrying in {NETWORK_RETRY_WAIT}s...")
                time.sleep(NETWORK_RETRY_WAIT)
                continue

            # Final network attempt or non-network error — return error
            if is_network:
                return f"SESSION_ERROR: Network error after {NETWORK_MAX_RETRIES} attempts\n{stderr}"
            prefix = "SESSION_ERROR_PERMANENT" if _is_permanent_error(stderr) else "SESSION_ERROR"
            return f"{prefix}: Exit code {proc.returncode}\n{stderr}\n{stdout}"

        except FileNotFoundError:
            return "SESSION_ERROR_PERMANENT: 'claude' command not found. Ensure Claude CLI is installed and in PATH."

    # Should not reach here, but safety net
    return "SESSION_ERROR: All retries exhausted"


# --- Result File Reading ---


def get_impl_result_path(project_dir: str) -> str:
    """Return absolute path to the implementation result file."""
    return os.path.join(project_dir, IMPL_RESULT_FILE)


def get_verify_result_path(project_dir: str) -> str:
    """Return absolute path to the verification result file."""
    return os.path.join(project_dir, VERIFY_RESULT_FILE)


def clean_result_files(project_dir: str) -> None:
    """Remove result files before a new attempt to prevent stale reads."""
    for path in [get_impl_result_path(project_dir), get_verify_result_path(project_dir)]:
        if os.path.exists(path):
            os.remove(path)


def _extract_json_from_text(text: str) -> str:
    """Extract JSON from text that may contain markdown fences or preamble.

    Agents sometimes wrap JSON in ```json ... ``` fences or add extra text.
    """
    # Try stripping markdown fences first
    fence_match = re.search(r"```(?:json)?\s*\n({.*?})\s*\n```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    # Try finding the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)
    return text


def read_json_result(file_path: str) -> tuple[dict | None, str]:
    """Read and parse a JSON result file.

    Returns (result_dict, error_message). On success, error_message is empty.
    On failure, result_dict is None and error_message explains why.

    Handles common agent output issues: markdown fences, preamble text,
    trailing commas.
    """
    if not os.path.exists(file_path):
        return None, f"Result file not found: {os.path.basename(file_path)}"
    try:
        with open(file_path, "r") as f:
            raw = f.read()
    except OSError as e:
        return None, f"Could not read {os.path.basename(file_path)}: {e}"

    # First try direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data, ""
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from surrounding text (markdown fences, preamble)
    extracted = _extract_json_from_text(raw)
    try:
        data = json.loads(extracted)
        if isinstance(data, dict):
            log(f"  Note: extracted JSON from non-clean output in {os.path.basename(file_path)}")
            return data, ""
    except json.JSONDecodeError:
        pass

    # Try fixing trailing commas (common LLM output issue)
    cleaned = re.sub(r",\s*([\]}])", r"\1", extracted)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            log(f"  Note: fixed trailing commas in {os.path.basename(file_path)}")
            return data, ""
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in {os.path.basename(file_path)}: {e}\nFirst 200 chars: {raw[:200]}"

    return None, f"Result file is not a JSON object: {os.path.basename(file_path)}"


def read_implementation_result(project_dir: str) -> tuple[dict | None, str]:
    """Read the implementation result JSON file.

    Returns (result_dict, error_message).
    """
    result, error = read_json_result(get_impl_result_path(project_dir))
    if result is not None:
        if "story_id" not in result:
            return None, "Implementation result missing 'story_id' field"
        if result.get("status") not in ("complete", "partial", "failed"):
            return None, f"Implementation result has invalid 'status': {result.get('status')}"
        for optional in ("learnings", "issues", "files_changed"):
            if optional not in result:
                log(f"  Note: implementation result missing optional field '{optional}'")
    return result, error


def read_verification_result(project_dir: str) -> tuple[dict | None, str]:
    """Read the verification result JSON file.

    Returns (result_dict, error_message).
    Expected keys: story_id, verdict, criteria, overall_notes, recommendations
    """
    result, error = read_json_result(get_verify_result_path(project_dir))
    if result is not None:
        # Normalize verdict to lowercase
        if "verdict" in result:
            result["verdict"] = str(result["verdict"]).lower()
        else:
            return None, "Verification result missing 'verdict' field"
        if result["verdict"] not in ("pass", "fail"):
            return None, f"Verification result has invalid 'verdict': {result['verdict']}"
        if not isinstance(result.get("criteria"), list):
            return None, "Verification result missing or invalid 'criteria' list"
        for optional in ("overall_notes", "recommendations"):
            if optional not in result:
                log(f"  Note: verification result missing optional field '{optional}'")
    return result, error


def extract_learnings_from_results(
    impl_result: dict | None, verify_result: dict | None
) -> list[str]:
    """Extract learnings from file-based implementation and verification results."""
    learnings = []

    if impl_result:
        for learning in impl_result.get("learnings", []):
            if learning:
                learnings.append(str(learning))
        for issue in impl_result.get("issues", []):
            if issue:
                learnings.append(f"Issue: {issue}")

    if verify_result:
        if verify_result.get("recommendations"):
            learnings.append(f"Verifier: {verify_result['recommendations']}")
        if verify_result.get("overall_notes"):
            learnings.append(f"Verifier note: {verify_result['overall_notes']}")

    return learnings


# --- Execution Log ---


def get_log_path(config: dict) -> str:
    """Return path to EXECUTION_LOG.md in the project."""
    return os.path.join(config["project_dir"], "kit_tools", "EXECUTION_LOG.md")


def init_execution_log(config: dict, epic_mode: bool = False) -> None:
    """Create or append a run header to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    mode = config["mode"]
    max_retries = config.get("max_retries", "unlimited")
    branch = config["branch_name"]
    now = now_iso()

    if epic_mode:
        epic_name = config["epic_name"]
        epic_specs = config["epic_specs"]
        header = f"""
## Run: epic/{epic_name} — {now[:10]}
- **Epic:** {epic_name}
- **Branch:** {branch}
- **Mode:** {mode} ({f'max {max_retries} retries' if max_retries else 'unlimited retries'})
- **Feature Specs:** {len(epic_specs)} total

"""
    else:
        feature_name = config.get("feature_name", "unknown")
        spec_name = os.path.basename(config["spec_path"])

        # Count total stories
        stories = parse_stories_from_spec(config["spec_path"])
        total = len(stories)
        complete = sum(1 for s in stories if s["completed"])

        header = f"""
## Run: {feature_name} — {now[:10]}
- **Feature Spec:** {spec_name}
- **Branch:** {branch}
- **Mode:** {mode} ({f'max {max_retries} retries' if max_retries else 'unlimited retries'})
- **Stories:** {total} total, {complete} complete at start

"""

    if not os.path.exists(log_path):
        with open(log_path, "w") as f:
            f.write("# Execution Log\n")
            f.write(f"> Last updated: {now[:10]}\n")
            f.write(header)
    else:
        with open(log_path, "a") as f:
            f.write(header)


def log_story_success(
    story: dict, attempt: int, config: dict, learnings: list,
    feature_name: str | None = None
) -> None:
    """Append a success entry to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    now = now_iso()
    feat_name = feature_name or config.get("feature_name", "feature")

    entry = f"### {story['id']}: {story['title']} (Attempt {attempt}) — PASS\n"
    entry += f"- Completed: {now}\n"
    entry += f"- Verified by: independent verifier session\n"
    if learnings:
        entry += f"- Learnings: {'; '.join(learnings)}\n"
    entry += f'- Committed: feat({feat_name}): {story["id"]} - {story["title"]}\n'
    entry += "\n"

    with open(log_path, "a") as f:
        f.write(entry)


def sanitize_failure_details(details: str) -> str:
    """Sanitize failure details to avoid leaking raw template/session content into the log."""
    # Strip SESSION_ERROR prefix (permanent or transient)
    for prefix in ("SESSION_ERROR_PERMANENT:", "SESSION_ERROR:"):
        if details.startswith(prefix):
            details = details[len(prefix):].strip()
            break
    # Take only the first meaningful line (avoid multi-line template dumps)
    first_line = details.split('\n')[0].strip()
    # If the first line is very long or looks like template content, truncate
    if len(first_line) > 200 or first_line.startswith('---'):
        first_line = first_line[:150] + "..."
    return first_line


def log_story_failure(
    story: dict, attempt: int, config: dict, failure_details: str, learnings: list
) -> None:
    """Append a failure entry to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    now = now_iso()

    clean_details = sanitize_failure_details(failure_details)

    entry = f"### {story['id']}: {story['title']} (Attempt {attempt}) — FAIL\n"
    entry += f"- Failed: {now}\n"
    entry += f"- Failure: {clean_details}\n"
    if learnings:
        entry += f"- Learnings: {'; '.join(learnings)}\n"
    entry += "- Working tree reset, retrying...\n"
    entry += "\n"

    with open(log_path, "a") as f:
        f.write(entry)


def log_completion(config: dict, state: dict) -> None:
    """Append a completion summary to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    now = now_iso()

    # Support both single and epic state structures
    if "specs" in state:
        # Epic mode: aggregate across all specs
        total_stories = 0
        completed = 0
        total_attempts = 0
        for spec_data in state.get("specs", {}).values():
            for sdata in spec_data.get("stories", {}).values():
                total_stories += 1
                if sdata.get("status") == "completed":
                    completed += 1
                total_attempts += sdata.get("attempts", 0)
    else:
        total_stories = len(state.get("stories", {}))
        completed = sum(
            1 for s in state.get("stories", {}).values()
            if s.get("status") == "completed"
        )
        total_attempts = sum(
            s.get("attempts", 0) for s in state.get("stories", {}).values()
        )

    total_sessions = state.get("sessions", {}).get("total", 0)

    entry = f"### Execution Complete — {now}\n"
    entry += f"- Stories: {completed}/{total_stories} completed\n"
    entry += f"- Total attempts: {total_attempts}\n"
    entry += f"- Total sessions: {total_sessions}\n"
    entry += "\n"

    with open(log_path, "a") as f:
        f.write(entry)


# --- Pause/Resume ---


def pause_file_exists(project_dir: str) -> bool:
    """Check for kit_tools/.pause_execution file."""
    return os.path.exists(os.path.join(project_dir, "kit_tools", ".pause_execution"))


def wait_for_pause_removal(project_dir: str, config: dict | None = None) -> None:
    """Poll until the pause file is removed, with timeout."""
    log("Paused. Remove kit_tools/.pause_execution to resume.")
    elapsed = 0
    last_reminder = 0
    while pause_file_exists(project_dir):
        time.sleep(PAUSE_POLL_INTERVAL)
        elapsed += PAUSE_POLL_INTERVAL
        if elapsed - last_reminder >= PAUSE_LOG_INTERVAL:
            log(f"  Still paused ({elapsed}s elapsed). Remove kit_tools/.pause_execution to resume.")
            last_reminder = elapsed
        if elapsed >= PAUSE_MAX_WAIT:
            log(f"  WARNING: Pause timeout reached ({PAUSE_MAX_WAIT}s). Auto-resuming.")
            if config:
                write_notification(
                    config, "pause_timeout",
                    "Pause timeout reached",
                    f"Auto-resumed after {PAUSE_MAX_WAIT}s pause.",
                    severity="warning",
                )
            pause_path = os.path.join(project_dir, "kit_tools", ".pause_execution")
            try:
                os.remove(pause_path)
            except OSError:
                pass
            break
    log("Pause file removed. Resuming execution.")


# --- Git ---


def run_git(args: list[str], project_dir: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run a git command with optional error logging.

    Args:
        args: Git subcommand and arguments (e.g., ["checkout", "main"]).
        project_dir: Working directory for the command.
        check: If True, log a warning when the command fails (non-fatal).
    """
    result = subprocess.run(
        ["git"] + args, cwd=project_dir, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        cmd_str = "git " + " ".join(args)
        log(f"  WARNING: git command failed: {cmd_str}\n    stderr: {result.stderr.strip()[:200]}")
    return result


def get_head_commit(project_dir: str) -> str:
    """Get the current HEAD commit hash."""
    result = run_git(["rev-parse", "HEAD"], project_dir)
    return result.stdout.strip()


def get_current_branch(project_dir: str) -> str:
    """Get the current branch name."""
    result = run_git(["branch", "--show-current"], project_dir)
    return result.stdout.strip()


def cleanup_attempt_branches(project_dir: str, feature_branch: str) -> None:
    """Delete any leaked attempt branches from previous crashed runs."""
    result = run_git(["branch", "--list", f"{feature_branch}-*-attempt-*"], project_dir)
    if result.returncode != 0 or not result.stdout.strip():
        return
    for line in result.stdout.strip().split("\n"):
        branch = line.strip().lstrip("* ")
        if branch:
            run_git(["branch", "-D", branch], project_dir)
            log(f"  Cleaned up leaked attempt branch: {branch}")


def create_attempt_branch(project_dir: str, feature_branch: str, story_id: str, attempt: int) -> str:
    """Create a temporary branch for this implementation attempt.

    Returns the attempt branch name.
    """
    attempt_branch = f"{feature_branch}-{story_id}-attempt-{attempt}"
    # Ensure we're on the feature branch
    run_git(["checkout", feature_branch], project_dir, check=True)
    # Delete the branch if it already exists (leaked from a previous crash)
    existing = run_git(["branch", "--list", attempt_branch], project_dir)
    if existing.stdout.strip():
        run_git(["branch", "-D", attempt_branch], project_dir)
        log(f"  Deleted pre-existing attempt branch: {attempt_branch}")
    # Create and switch to the attempt branch
    run_git(["checkout", "-b", attempt_branch], project_dir, check=True)
    log(f"  Created attempt branch: {attempt_branch}")
    return attempt_branch


def get_attempt_diff(project_dir: str, feature_branch: str, attempt_branch: str) -> str:
    """Capture the diff between the feature branch and the attempt branch.

    Used to provide patch-based retry context for subsequent attempts.
    """
    result = run_git(["diff", f"{feature_branch}...{attempt_branch}"], project_dir)
    diff = result.stdout.strip() if result.returncode == 0 else ""
    # Truncate if too large
    if len(diff) > 10000:
        diff = diff[:10000] + "\n\n... [diff truncated at 10KB] ..."
    return diff


def get_diff_stat(project_dir: str, feature_branch: str, attempt_branch: str) -> str:
    """Get a summary of changes between the feature branch and attempt branch.

    Returns the output of `git diff --stat feature...attempt`.
    """
    result = run_git(["diff", "--stat", f"{feature_branch}...{attempt_branch}"], project_dir)
    return result.stdout.strip() if result.returncode == 0 else ""


def merge_attempt_branch(project_dir: str, feature_branch: str, attempt_branch: str) -> bool:
    """Merge a successful attempt branch into the feature branch.

    Returns True if merge succeeded.
    """
    # Switch to the feature branch
    run_git(["checkout", feature_branch], project_dir, check=True)
    # Merge the attempt branch (fast-forward if possible)
    result = run_git(["merge", attempt_branch, "--no-edit"], project_dir)
    if result.returncode != 0:
        log(f"  Merge failed: {result.stderr[:200]}")
        return False
    # Delete the attempt branch
    run_git(["branch", "-d", attempt_branch], project_dir, check=True)
    log(f"  Merged {attempt_branch} into {feature_branch}")
    return True


def delete_attempt_branch(project_dir: str, feature_branch: str, attempt_branch: str) -> str:
    """Delete a failed attempt branch and return to the feature branch.

    Returns the captured diff (for retry context) before deleting.
    """
    # Capture the diff before deleting
    diff = get_attempt_diff(project_dir, feature_branch, attempt_branch)
    # Switch back to feature branch
    run_git(["checkout", feature_branch], project_dir, check=True)
    # Force-delete the attempt branch
    run_git(["branch", "-D", attempt_branch], project_dir, check=True)
    log(f"  Deleted failed attempt branch: {attempt_branch}")
    return diff


def verify_branch_base(project_dir: str) -> bool:
    """Verify the feature branch is based on main."""
    result = run_git(["merge-base", "--is-ancestor", "main", "HEAD"], project_dir)
    return result.returncode == 0


def commit_tracking_files(project_dir: str, feature_name: str) -> None:
    """Commit tracking files (execution log, audit findings) after completion."""
    files_to_commit = []
    for rel_path in [
        "kit_tools/EXECUTION_LOG.md",
        "kit_tools/AUDIT_FINDINGS.md",
    ]:
        full_path = os.path.join(project_dir, rel_path)
        if os.path.exists(full_path):
            files_to_commit.append(rel_path)

    if not files_to_commit:
        return

    run_git(["add"] + files_to_commit, project_dir, check=True)
    run_git(
        ["commit", "-m", f"chore({feature_name}): execution log and audit findings"],
        project_dir, check=True
    )


def is_validation_clean(project_dir: str) -> bool:
    """Check if the last validation run was clean (no critical findings, no pause).

    Returns False if a pause file exists or AUDIT_FINDINGS.md contains
    unresolved critical findings.
    """
    if pause_file_exists(project_dir):
        return False
    audit_path = os.path.join(project_dir, "kit_tools", "AUDIT_FINDINGS.md")
    if not os.path.exists(audit_path):
        return True
    try:
        with open(audit_path, "r") as f:
            content = f.read()
        # Look for unresolved critical findings (severity: critical without a ✅ resolved marker)
        if re.search(r"(?i)severity:\s*critical", content) and "✅" not in content:
            return False
    except OSError:
        pass
    return True


def _cleanup_execution_artifacts(project_dir: str) -> None:
    """Remove execution state files after completion."""
    for rel_path in [
        os.path.join("kit_tools", "specs", ".execution-state.json"),
        os.path.join("kit_tools", "specs", ".execution-config.json"),
        os.path.join("kit_tools", ".pause_execution"),
    ]:
        full = os.path.join(project_dir, rel_path)
        if os.path.exists(full):
            try:
                os.remove(full)
            except OSError:
                pass


def _build_pr_body(config: dict, state: dict) -> str:
    """Build a PR description body from execution state."""
    lines = ["## Summary\n"]
    if config.get("epic_specs"):
        # Epic mode
        epic_name = config.get("epic_name", "epic")
        specs = config.get("epic_specs", [])
        lines.append(f"Epic **{epic_name}** — {len(specs)} feature specs completed.\n")
        for spec_info in specs:
            lines.append(f"- {spec_info['feature_name']}")
        lines.append("")
    else:
        # Standalone mode
        feature_name = config.get("feature_name", "feature")
        stories = state.get("stories", {})
        story_count = len([s for s in stories.values() if s.get("status") == "completed"])
        total_attempts = sum(s.get("attempts", 0) for s in stories.values())
        sessions = state.get("sessions", {})
        lines.append(f"Feature **{feature_name}** — {story_count} stories completed.")
        lines.append(f"- Total attempts: {total_attempts}")
        lines.append(f"- Sessions: {sessions.get('total', 0)} total "
                      f"({sessions.get('implementation', 0)} impl, "
                      f"{sessions.get('verification', 0)} verify, "
                      f"{sessions.get('validation', 0)} validation)")
        lines.append("")

    lines.append("---")
    lines.append("Generated by KitTools autonomous execution")
    return "\n".join(lines)


def complete_feature(config: dict, state: dict, validation_clean: bool) -> None:
    """Handle post-execution completion based on the configured strategy.

    Strategies:
        "pr"    — Push branch, create GitHub PR
        "merge" — Merge to main (blocked if validation found critical issues)
        "none"  — Leave branch as-is
    """
    strategy = config.get("completion_strategy", "none")
    project_dir = config["project_dir"]
    branch = config["branch_name"]
    feature_name = config.get("feature_name") or config.get("epic_name", "feature")

    # Archive spec if single mode and spec still exists
    if not config.get("epic_specs"):
        spec_path = config.get("spec_path", "")
        if spec_path and os.path.exists(spec_path):
            archive_spec(project_dir, spec_path, feature_name)
            run_git(
                ["commit", "-m", f"chore({feature_name}): archive feature spec", "--allow-empty"],
                project_dir, check=True
            )

    # Commit tracking files
    commit_tracking_files(project_dir, feature_name)

    # --- Merge strategy ---
    if strategy == "merge":
        if not validation_clean:
            log("Validation found critical issues — merge blocked. Falling back to PR.")
            write_notification(
                config, "completion_fallback",
                "Merge blocked — falling back to PR",
                f"Critical validation findings prevent auto-merge for {feature_name}.",
                severity="warning",
            )
            strategy = "pr"
        else:
            # Attempt merge
            checkout_result = run_git(["checkout", "main"], project_dir)
            if checkout_result.returncode != 0:
                log(f"Failed to checkout main: {checkout_result.stderr.strip()[:200]}")
                log("Falling back to PR strategy.")
                run_git(["checkout", branch], project_dir)
                strategy = "pr"
            else:
                merge_result = run_git(["merge", branch, "--no-edit"], project_dir)
                if merge_result.returncode != 0:
                    log(f"Merge failed: {merge_result.stderr.strip()[:200]}")
                    log("Aborting merge, falling back to PR strategy.")
                    run_git(["merge", "--abort"], project_dir)
                    run_git(["checkout", branch], project_dir)
                    write_notification(
                        config, "completion_fallback",
                        "Merge failed — falling back to PR",
                        f"Merge conflict for {feature_name}. Branch left as-is.",
                        severity="warning",
                    )
                    strategy = "pr"
                else:
                    # Merge succeeded — delete feature branch
                    run_git(["branch", "-d", branch], project_dir)
                    log(f"Merged {branch} into main and deleted feature branch.")
                    write_notification(
                        config, "feature_merged",
                        f"Feature merged: {feature_name}",
                        f"Branch {branch} merged to main and deleted.",
                        severity="info",
                    )
                    _cleanup_execution_artifacts(project_dir)
                    kill_tmux_session(config)
                    return

    # --- PR strategy ---
    if strategy == "pr":
        # Check gh availability
        gh_available = True
        try:
            gh_check = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=15
            )
            if gh_check.returncode != 0:
                gh_available = False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            gh_available = False

        if not gh_available:
            log("gh CLI not available or not authenticated. Leaving branch as-is.")
            write_notification(
                config, "completion_fallback",
                "PR creation skipped — gh unavailable",
                f"Install/authenticate gh CLI to create PRs. Branch {branch} is ready.",
                severity="warning",
            )
            strategy = "none"
        else:
            # Push and create PR
            push_result = run_git(["push", "-u", "origin", branch], project_dir)
            if push_result.returncode != 0:
                log(f"Push failed: {push_result.stderr.strip()[:200]}")
                log("Branch left as-is.")
                write_notification(
                    config, "completion_fallback",
                    "Push failed — PR not created",
                    f"Could not push {branch}. Create PR manually.",
                    severity="warning",
                )
            else:
                pr_title = f"feat({feature_name}): autonomous implementation"
                pr_body = _build_pr_body(config, state)
                try:
                    pr_result = subprocess.run(
                        ["gh", "pr", "create", "--title", pr_title, "--body", pr_body],
                        capture_output=True, text=True, timeout=30,
                        cwd=project_dir
                    )
                    if pr_result.returncode == 0:
                        pr_url = pr_result.stdout.strip()
                        log(f"PR created: {pr_url}")
                        write_notification(
                            config, "pr_created",
                            f"PR created: {feature_name}",
                            f"PR: {pr_url}",
                            severity="info",
                        )
                    else:
                        log(f"PR creation failed: {pr_result.stderr.strip()[:200]}")
                        log(f"Branch {branch} has been pushed — create PR manually.")
                except (subprocess.TimeoutExpired, OSError) as e:
                    log(f"PR creation error: {e}")
                    log(f"Branch {branch} has been pushed — create PR manually.")

    # --- None strategy (or fallback) ---
    if strategy == "none":
        log(f"Branch {branch} left as-is. No merge or PR created.")

    _cleanup_execution_artifacts(project_dir)
    kill_tmux_session(config)


# --- Test Command Detection ---


def parse_test_mapping(project_dir: str) -> dict[str, str]:
    """Parse test_mapping from TESTING_GUIDE.md if available.

    Looks for a YAML code block under a '## Test Mapping' or 'test_mapping:' section.
    Returns a dict mapping source glob patterns to test file patterns.
    """
    testing_guide = os.path.join(project_dir, "kit_tools", "testing", "TESTING_GUIDE.md")
    if not os.path.exists(testing_guide):
        return {}
    try:
        with open(testing_guide, "r") as f:
            content = f.read()
        # Look for test_mapping in a YAML code block
        match = re.search(
            r"```(?:ya?ml)?\s*\n(test_mapping:\s*\n.+?)```",
            content, re.DOTALL
        )
        if match:
            parsed = yaml.safe_load(match.group(1))
            if isinstance(parsed, dict) and "test_mapping" in parsed:
                mapping = parsed["test_mapping"]
                if isinstance(mapping, dict):
                    return {str(k): str(v) for k, v in mapping.items()}
    except (OSError, yaml.YAMLError):
        pass
    return {}


def detect_related_tests(
    changed_files: list[str], project_dir: str, test_command: str | None
) -> str | None:
    """Derive a targeted test command from changed files.

    Strategy:
    1. Check TESTING_GUIDE.md for explicit test_mapping
    2. Apply heuristic matching (source file → test file by naming convention)
    3. Return targeted command if matching test files exist, else None (caller falls back)
    """
    if not changed_files or not test_command:
        return None

    # Filter to source files (skip configs, docs, test files themselves)
    source_files = []
    for f in changed_files:
        if not f.strip():
            continue
        # Skip files that are already tests
        basename = os.path.basename(f)
        if basename.startswith("test_") or basename.endswith(("_test.py", ".test.ts", ".test.js", ".test.tsx", ".test.jsx", ".spec.ts", ".spec.js")):
            continue
        # Skip non-code files
        if f.endswith((".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".lock")):
            continue
        source_files.append(f)

    if not source_files:
        return None

    # 1. Try explicit test_mapping from TESTING_GUIDE.md
    test_mapping = parse_test_mapping(project_dir)
    matched_tests: set[str] = set()

    if test_mapping:
        import fnmatch
        for src_file in source_files:
            for pattern, test_pattern in test_mapping.items():
                if fnmatch.fnmatch(src_file, pattern):
                    # test_pattern may contain multiple space-separated patterns
                    for tp in test_pattern.split():
                        matched_tests.add(tp)

    # 2. Heuristic matching for files not caught by explicit mapping
    import glob as glob_mod
    for src_file in source_files:
        basename = os.path.basename(src_file)
        name_no_ext = os.path.splitext(basename)[0]
        ext = os.path.splitext(basename)[1]

        candidates = []
        if ext == ".py":
            # Python: foo.py → test_foo.py, tests/test_foo.py, tests/**/test_foo.py
            candidates = [
                f"**/test_{name_no_ext}.py",
                f"**/{name_no_ext}_test.py",
            ]
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            # JS/TS: foo.ts → foo.test.ts, foo.spec.ts, __tests__/foo.test.ts
            for test_ext in (".test", ".spec"):
                candidates.append(f"**/{name_no_ext}{test_ext}{ext}")

        for pattern in candidates:
            matches = glob_mod.glob(
                os.path.join(project_dir, pattern), recursive=True
            )
            for m in matches:
                matched_tests.add(os.path.relpath(m, project_dir))

    if not matched_tests:
        return None

    # Build targeted command
    # Verify matched test files actually exist (glob patterns from mapping may not)
    existing_tests = []
    for t in matched_tests:
        if "*" in t or "?" in t:
            # It's a glob pattern — check if it matches anything
            matches = glob_mod.glob(os.path.join(project_dir, t), recursive=True)
            if matches:
                existing_tests.append(t)
        elif os.path.exists(os.path.join(project_dir, t)):
            existing_tests.append(t)

    if not existing_tests:
        return None

    # Build the targeted command based on runner type
    test_files_str = " ".join(sorted(existing_tests))
    if "pytest" in test_command:
        return f"python3 -m pytest {test_files_str} -x"
    elif test_command == "npm test" or "jest" in test_command:
        # Jest accepts file patterns
        return f"npx jest {test_files_str} --bail"
    elif "vitest" in test_command:
        return f"npx vitest run {test_files_str} --bail 1"
    else:
        # Unknown runner — can't scope, return None to fall back
        return None


def make_quiet(test_command: str) -> str:
    """Add quiet flags for full-suite runs. Suppresses PASSED noise, preserves failure tracebacks."""
    if not test_command:
        return test_command
    if "pytest" in test_command:
        # Remove -v if present, add -q --tb=short (preserves failure tracebacks)
        cmd = re.sub(r"\s+-v\b", "", test_command)
        return f"{cmd} -q --tb=short"
    # jest and vitest default output already focuses on failures
    return test_command


def detect_test_command(project_dir: str) -> str | None:
    """Auto-detect the project's test command.

    Checks in order:
    1. package.json "test" script (skip if it's the npm default)
    2. pyproject.toml [tool.pytest] or [tool.poetry.scripts]
    3. pytest.ini
    4. Makefile "test" target
    5. kit_tools/testing/TESTING_GUIDE.md Quick Start section

    Returns the test command string, or None if not detected.
    """
    # 1. package.json
    pkg_json = os.path.join(project_dir, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, "r") as f:
                pkg = json.load(f)
            test_script = pkg.get("scripts", {}).get("test", "")
            # Skip npm default placeholder
            if test_script and 'echo "Error: no test specified"' not in test_script:
                return f"npm test"
        except (json.JSONDecodeError, OSError):
            pass

    # 2. pyproject.toml
    pyproject = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, "r") as f:
                content = f.read()
            # Check for pytest configuration
            if "[tool.pytest" in content:
                return "python3 -m pytest"
            # Check for poetry test script
            if "[tool.poetry.scripts]" in content and "test" in content:
                return "poetry run pytest"
        except OSError:
            pass

    # 3. pytest.ini
    if os.path.exists(os.path.join(project_dir, "pytest.ini")):
        return "python3 -m pytest"

    # 4. Makefile
    makefile = os.path.join(project_dir, "Makefile")
    if os.path.exists(makefile):
        try:
            with open(makefile, "r") as f:
                content = f.read()
            if re.search(r"^test\s*:", content, re.MULTILINE):
                return "make test"
        except OSError:
            pass

    # 5. kit_tools/testing/TESTING_GUIDE.md
    testing_guide = os.path.join(project_dir, "kit_tools", "testing", "TESTING_GUIDE.md")
    if os.path.exists(testing_guide):
        try:
            with open(testing_guide, "r") as f:
                content = f.read()
            # Look for a code block in the Quick Start section
            qs_match = re.search(
                r"##\s*Quick Start.*?```(?:\w*)\n(.+?)```",
                content, re.DOTALL | re.IGNORECASE
            )
            if qs_match:
                # Take the first non-empty line from the code block
                for line in qs_match.group(1).strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
        except OSError:
            pass

    return None


def make_fail_fast(test_command: str) -> str:
    """Append fail-fast flags to known test runners."""
    if not test_command:
        return test_command
    if "pytest" in test_command:
        return f"{test_command} -x"
    if test_command in ("npm test",) or "npx jest" in test_command:
        return f"{test_command} -- --bail"
    if "vitest" in test_command:
        return f"{test_command} --bail 1"
    return test_command


# --- Utilities ---


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


# --- Story Execution Loop ---


def execute_spec_stories(
    spec_path: str, feature_name: str, config: dict, state: dict,
    spec_key: str | None = None
) -> dict:
    """Execute all stories in a single feature spec. Returns updated state.

    Args:
        spec_path: Absolute path to the feature spec file.
        feature_name: Feature name for commit messages.
        config: Orchestrator config dict.
        state: Execution state dict.
        spec_key: If set, story state lives under state["specs"][spec_key] (epic mode).
                 If None, story state lives under state["stories"] (single mode).
    """
    project_dir = config["project_dir"]
    mode = config["mode"]
    max_retries = config.get("max_retries")

    # Auto-detect test command once per feature spec execution
    test_command = detect_test_command(project_dir)
    fail_fast_test = make_fail_fast(test_command) if test_command else None
    if test_command:
        log(f"  Detected test command: {test_command}")

    # Determine which stories_state dict to use for find_next_uncompleted_story
    if spec_key is not None:
        stories_state = state["specs"][spec_key]
    else:
        stories_state = state

    while True:
        # Check pause file between stories
        if pause_file_exists(project_dir):
            wait_for_pause_removal(project_dir, config=config)

        # Find next uncompleted story
        story = find_next_uncompleted_story(spec_path, stories_state)
        if not story:
            return state  # All stories done

        story_state_entry = stories_state.get("stories", {}).get(story["id"], {})
        attempt = story_state_entry.get("attempts", 0)
        feature_branch = config["branch_name"]

        while True:
            attempt += 1

            # Check retry limit
            if max_retries is not None and attempt > max_retries:
                if mode == "guarded":
                    log(f"Story {story['id']} failed after {max_retries} attempts.")
                    log("Guarded mode: waiting for user input...")
                    try:
                        input("Press Enter to retry, or Ctrl+C to stop: ")
                    except (KeyboardInterrupt, EOFError):
                        log("User stopped execution.")
                        state["status"] = "paused"
                        save_state(state, config)
                        commit_tracking_files(project_dir, feature_name)
                        clean_result_files(project_dir)
                        sys.exit(0)
                    attempt = 1  # Reset for new round
                    continue
                else:
                    log(f"Story {story['id']} exceeded max retries ({max_retries}). Stopping.")
                    state["status"] = "failed"
                    update_state_story(
                        state, story["id"], "failed", attempt - 1,
                        failure=f"Exceeded max retries ({max_retries})",
                        spec_key=spec_key
                    )
                    save_state(state, config)
                    write_notification(
                        config, "story_failed",
                        f"Story {story['id']} failed",
                        f"{story['id']}: {story['title']} exceeded {max_retries} retries",
                        severity="critical",
                    )
                    commit_tracking_files(project_dir, feature_name)
                    clean_result_files(project_dir)
                    sys.exit(1)

            # Clean result files before each attempt
            clean_result_files(project_dir)

            # --- Capture pre-attempt HEAD for unambiguous diffs ---
            pre_attempt_head = get_head_commit(project_dir)

            # --- Create attempt branch ---
            attempt_branch = create_attempt_branch(
                project_dir, feature_branch, story["id"], attempt
            )

            # --- Implementation session ---
            log(f"Implementing {story['id']}: {story['title']} (attempt {attempt})...")
            update_state_story(state, story["id"], "in_progress", attempt, spec_key=spec_key)
            save_state(state, config)

            prompt = build_implementation_prompt(
                story, config, state, attempt,
                feature_name=feature_name, spec_path=spec_path, spec_key=spec_key
            )
            prompt = check_and_trim_prompt(prompt, "implementation")

            # Estimate input tokens
            prompt_chars = len(prompt)
            impl_output = run_claude_session(prompt, project_dir)
            output_chars = len(impl_output)

            state["sessions"]["total"] += 1
            state["sessions"]["implementation"] += 1
            # Track token estimates
            token_est = state.setdefault("token_estimates", {"input": 0, "output": 0})
            token_est["input"] += prompt_chars // 4
            token_est["output"] += output_chars // 4
            log(f"  Session tokens: ~{prompt_chars // 4000}k input, ~{output_chars // 4000}k output")
            save_state(state, config)

            # Check for session errors
            if impl_output.startswith("SESSION_ERROR_PERMANENT:"):
                log(f"  Permanent session error: {impl_output[:200]}")
                learnings = [f"Permanent error: {impl_output[:200]}"]
                log_story_failure(story, attempt, config, impl_output[:500], learnings)
                update_state_story(
                    state, story["id"], "failed", attempt, learnings, impl_output[:500],
                    spec_key=spec_key
                )
                state["status"] = "failed"
                save_state(state, config)
                write_notification(
                    config, "story_failed",
                    f"Story {story['id']} permanent error",
                    f"{story['id']}: {impl_output[:200]}",
                    severity="critical",
                )
                delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                clean_result_files(project_dir)
                sys.exit(1)

            if impl_output.startswith("SESSION_ERROR:"):
                log(f"  Implementation session error: {impl_output[:200]}")
                learnings = [f"Session error: {impl_output[:200]}"]
                log_story_failure(story, attempt, config, impl_output[:500], learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt, learnings, impl_output[:500],
                    spec_key=spec_key
                )
                save_state(state, config)
                # Delete the failed attempt branch (no diff to capture on session error)
                delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                clean_result_files(project_dir)
                continue

            # --- Read implementation result from file ---
            impl_result, impl_error = read_implementation_result(project_dir)
            if impl_error:
                log(f"  Implementation result: {impl_error}")

            # --- Get files changed from git (for verifier) ---
            git_files_result = run_git(
                ["diff", "--name-only", f"{pre_attempt_head}..HEAD"], project_dir
            )
            files_changed_from_git = git_files_result.stdout.strip() if git_files_result.returncode == 0 else ""

            # --- Get diff stat (for verifier) ---
            diff_stat_result = run_git(
                ["diff", "--stat", f"{pre_attempt_head}..HEAD"], project_dir
            )
            diff_stat = diff_stat_result.stdout.strip() if diff_stat_result.returncode == 0 else ""

            # --- Capture inline diff content (for verifier) ---
            diff_content_result = run_git(
                ["diff", f"{pre_attempt_head}..HEAD"], project_dir
            )
            raw_diff = diff_content_result.stdout.strip() if diff_content_result.returncode == 0 else ""
            if len(raw_diff) <= DIFF_CONTENT_MAX:
                diff_content = raw_diff
            else:
                diff_content = (
                    f"[Diff truncated — {len(raw_diff)} chars exceeds {DIFF_CONTENT_MAX} limit. "
                    f"Use the Read tool to examine full files.]\n\n"
                    f"Diff stat:\n{diff_stat}"
                )

            # --- Verification session ---
            log(f"  Verifying {story['id']}...")
            verify_prompt = build_verification_prompt(
                story, config, files_changed_from_git,
                diff_stat=diff_stat, test_command=fail_fast_test, spec_path=spec_path,
                diff_content=diff_content
            )
            verify_prompt = check_and_trim_prompt(verify_prompt, "verification")

            verify_prompt_chars = len(verify_prompt)
            verify_output = run_claude_session(verify_prompt, project_dir)
            verify_output_chars = len(verify_output)

            state["sessions"]["total"] += 1
            state["sessions"]["verification"] += 1
            token_est["input"] += verify_prompt_chars // 4
            token_est["output"] += verify_output_chars // 4
            log(f"  Session tokens: ~{verify_prompt_chars // 4000}k input, ~{verify_output_chars // 4000}k output")
            save_state(state, config)

            # --- Check for verification session errors ---
            if is_session_error(verify_output):
                log(f"  Verification session error: {verify_output[:200]}")
                learnings = extract_learnings_from_results(impl_result, None)
                learnings.append(f"Verify session error: {verify_output[:200]}")
                log_story_failure(story, attempt, config, verify_output[:500], learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, verify_output[:500], spec_key=spec_key
                )
                save_state(state, config)
                attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                save_state(state, config)
                clean_result_files(project_dir)
                continue

            # --- Read verification result from file ---
            verdict, verify_error = read_verification_result(project_dir)

            if verify_error:
                # Result file missing or invalid — treat as retryable failure
                log(f"  Verification result error: {verify_error}")
                learnings = extract_learnings_from_results(impl_result, None)
                log_story_failure(story, attempt, config, verify_error, learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, verify_error, spec_key=spec_key
                )
                save_state(state, config)
                # Capture diff as retry context, then delete attempt branch
                attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                save_state(state, config)
                clean_result_files(project_dir)
                continue

            if verdict["verdict"] == "pass":
                learnings = extract_learnings_from_results(impl_result, verdict)
                log(f"  {story['id']} PASSED (attempt {attempt})")
                # Merge attempt branch into feature branch
                merge_ok = merge_attempt_branch(project_dir, feature_branch, attempt_branch)
                if not merge_ok:
                    log(f"  Merge conflict — aborting merge, will retry implementation.")
                    run_git(["merge", "--abort"], project_dir, check=True)
                    learnings.append("Merge conflict on attempt branch — retry with fresh approach")
                    log_story_failure(story, attempt, config, "Merge conflict", learnings)
                    update_state_story(
                        state, story["id"], "retrying", attempt,
                        learnings, "Merge conflict", spec_key=spec_key
                    )
                    save_state(state, config)
                    attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                    _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                    save_state(state, config)
                    clean_result_files(project_dir)
                    continue
                # Update feature spec checkboxes on the feature branch
                if update_spec_checkboxes(spec_path, story["id"]):
                    log(f"  Updated feature spec checkboxes for {story['id']}")
                    run_git(["add", spec_path], project_dir, check=True)
                    run_git(
                        ["commit", "-m", f"chore({feature_name}): mark {story['id']} criteria complete"],
                        project_dir, check=True
                    )
                log_story_success(story, attempt, config, learnings, feature_name=feature_name)
                update_state_story(
                    state, story["id"], "completed", attempt, learnings, spec_key=spec_key
                )
                save_state(state, config)
                write_notification(
                    config, "story_complete",
                    f"Story {story['id']} passed",
                    f"{story['id']}: {story['title']} (attempt {attempt})",
                    severity="info",
                )
                clean_result_files(project_dir)
                break  # Move to next story
            else:
                failure_details = verdict.get("recommendations", "Verification failed")
                learnings = extract_learnings_from_results(impl_result, verdict)
                log(f"  {story['id']} FAILED verification (attempt {attempt})")
                log(f"  Reason: {str(failure_details)[:200]}")
                log_story_failure(story, attempt, config, str(failure_details), learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, str(failure_details), spec_key=spec_key
                )
                save_state(state, config)
                # Capture diff as retry context, then delete attempt branch
                attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                save_state(state, config)
                clean_result_files(project_dir)
                # Loop continues to next attempt

    return state


# --- Single Feature Spec Mode ---


def run_single_spec(config: dict) -> None:
    """Execute a single feature spec (original behavior, backwards compatible)."""
    state, is_rerun = load_or_create_state(config)
    save_state(state, config)

    project_dir = config["project_dir"]
    spec_path = config["spec_path"]
    mode = config["mode"]
    max_retries = config.get("max_retries")

    log(f"Starting execution: {os.path.basename(spec_path)}")
    log(f"Mode: {mode}, Max retries: {max_retries or 'unlimited'}")
    log(f"Branch: {config['branch_name']}")

    # Clean up leaked attempt branches from previous crashes
    cleanup_attempt_branches(project_dir, config["branch_name"])

    # Verify branch is based on main
    if not verify_branch_base(project_dir):
        log(f"WARNING: Branch {config['branch_name']} does not appear to be based on main.")
        log("This may result in unrelated commits in the feature branch.")
        log("Consider rebasing onto main before continuing.")

    # Add re-run separator to execution log if resuming
    if is_rerun:
        log_path = get_log_path(config)
        if os.path.exists(log_path):
            with open(log_path, "a") as f:
                f.write("\n---\n> Previous run ended. New run starting below.\n---\n\n")

    # Initialize execution log
    init_execution_log(config)

    # Execute all stories
    execute_spec_stories(spec_path, config.get("feature_name", "feature"), config, state)

    # All stories complete
    log("All stories complete!")

    # Mark completed and log BEFORE spawning validation.
    # validate-implementation -> complete-implementation will clean up state files,
    # so we must not write to them after the validation session returns.
    state["status"] = "completed"
    save_state(state, config)
    log_completion(config, state)
    feature_label = config.get("feature_name", "feature")
    write_notification(
        config, "execution_complete",
        "Execution complete",
        f"All stories passed for {feature_label}",
        severity="info",
    )

    # Run implementation validation (may auto-invoke complete-implementation)
    spec_basename = os.path.basename(spec_path)
    branch = config["branch_name"]
    log("Running implementation validation...")
    validate_prompt = (
        f"Run /kit-tools:validate-implementation for feature spec {spec_basename}. "
        f"Mode: autonomous. Branch: {branch}."
    )
    validate_output = run_claude_session(validate_prompt, project_dir)

    if is_session_error(validate_output):
        log(f"Validation session error: {validate_output[:200]}")
    else:
        log("Implementation validation complete.")

    # Determine if validation was clean
    validation_clean = not is_session_error(validate_output) and is_validation_clean(project_dir)

    # Handle pause file based on completion strategy
    strategy = config.get("completion_strategy", "none")
    if pause_file_exists(project_dir):
        if strategy == "merge":
            log("Critical findings detected — merge will be blocked.")
            # Remove pause file since complete_feature handles the fallback
            try:
                os.remove(os.path.join(project_dir, "kit_tools", ".pause_execution"))
            except OSError:
                pass
        else:
            write_notification(
                config, "execution_paused",
                "Execution paused",
                f"Critical validation findings for {feature_label}. Review AUDIT_FINDINGS.md.",
                severity="warning",
            )
            wait_for_pause_removal(project_dir, config=config)
            log("Resuming after pause. Proceeding to completion.")

    complete_feature(config, state, validation_clean)


# --- Epic Mode ---


def run_epic(config: dict) -> None:
    """Execute an epic: multiple feature specs in sequence on a shared branch."""
    state, is_rerun = load_or_create_epic_state(config)
    save_state(state, config)

    project_dir = config["project_dir"]
    epic_name = config["epic_name"]
    epic_specs = config["epic_specs"]

    log(f"Starting epic: {epic_name} ({len(epic_specs)} feature specs)")
    log(f"Branch: {config['branch_name']}")

    # Clean up leaked attempt branches from previous crashes
    cleanup_attempt_branches(project_dir, config["branch_name"])

    if not verify_branch_base(project_dir):
        log(f"WARNING: Branch {config['branch_name']} may not be based on main.")

    # Add re-run separator to execution log if resuming
    if is_rerun:
        log_path = get_log_path(config)
        if os.path.exists(log_path):
            with open(log_path, "a") as f:
                f.write("\n---\n> Previous epic run ended. New run starting below.\n---\n\n")

    init_execution_log(config, epic_mode=True)

    for i, spec_info in enumerate(epic_specs):
        spec_path = spec_info["spec_path"]
        feature_name = spec_info["feature_name"]
        is_final = spec_info.get("epic_final", False)
        spec_basename = os.path.basename(spec_path)

        # Skip already completed specs (resume support)
        spec_entry = state["specs"].get(spec_basename, {})
        if spec_entry.get("status") == "completed":
            log(f"Skipping {spec_basename} (already completed)")
            continue

        # Hard gate: verify dependencies are archived
        deps_ok, missing = check_dependencies_archived(project_dir, spec_path)
        if not deps_ok:
            log(f"ERROR: Dependencies not met for {spec_basename}: {missing}")
            log("Cannot continue epic execution.")
            state["status"] = "blocked"
            save_state(state, config)
            write_notification(
                config, "execution_paused",
                "Epic blocked on dependencies",
                f"{spec_basename} blocked — missing: {', '.join(missing)}",
                severity="critical",
            )
            commit_tracking_files(project_dir, epic_name)
            clean_result_files(project_dir)
            sys.exit(1)

        log(f"--- Feature spec {i+1}/{len(epic_specs)}: {spec_basename} ---")

        # Initialize feature spec state entry
        if spec_basename not in state["specs"]:
            state["specs"][spec_basename] = {
                "feature_name": feature_name,
                "status": "in_progress",
                "started_at": now_iso(),
                "stories": {},
            }
        state["current_spec"] = spec_basename
        save_state(state, config)

        # Execute all stories in this feature spec
        execute_spec_stories(spec_path, feature_name, config, state, spec_key=spec_basename)

        # Feature spec stories complete — validate
        log(f"  All stories complete for {spec_basename}. Validating...")
        validate_prompt = (
            f"Run /kit-tools:validate-implementation for feature spec {spec_basename}. "
            f"Mode: autonomous. Branch: {config['branch_name']}. "
            f"This is part of an epic — do NOT invoke complete-implementation."
        )
        validate_output = run_claude_session(validate_prompt, project_dir)
        state["sessions"]["total"] += 1
        state["sessions"]["validation"] += 1

        if is_session_error(validate_output):
            log(f"  Validation error: {validate_output[:200]}")
            # Continue anyway — validation is informational

        # Check for pause file (created by validate-implementation if critical findings exist)
        if pause_file_exists(project_dir):
            log(f"  Critical validation findings for {spec_basename}. Pausing.")
            wait_for_pause_removal(project_dir, config=config)
            log("  Resuming after pause.")

        # Commit tracking files for this feature spec
        commit_tracking_files(project_dir, feature_name)

        # Tag checkpoint
        tag_checkpoint(project_dir, epic_name, feature_name)

        # Archive feature spec
        archive_spec(project_dir, spec_path, feature_name)

        # Commit archive + tag
        run_git(
            ["commit", "-m", f"chore({epic_name}): complete {feature_name}", "--allow-empty"],
            project_dir, check=True
        )

        # Update state
        state["specs"][spec_basename]["status"] = "completed"
        state["specs"][spec_basename]["completed_at"] = now_iso()
        save_state(state, config)

        log(f"  {spec_basename} complete. Tagged: {epic_name}/{feature_name}-complete")
        write_notification(
            config, "spec_complete",
            f"Feature spec complete: {feature_name}",
            f"{spec_basename} ({i+1}/{len(epic_specs)}) complete in epic {epic_name}",
            severity="info",
        )

        # Pause between feature specs if configured
        if config.get("epic_pause_between_specs") and not is_final:
            pause_path = os.path.join(project_dir, "kit_tools", ".pause_execution")
            with open(pause_path, "w") as f:
                f.write(f"Epic paused after {spec_basename}. Remove this file to continue.\n")
            log(f"  Pausing between feature specs. Review {spec_basename} results, then:")
            log(f"    rm kit_tools/.pause_execution")
            write_notification(
                config, "execution_paused",
                "Epic paused between feature specs",
                f"Paused after {spec_basename}. Remove pause file to continue.",
                severity="warning",
            )
            wait_for_pause_removal(project_dir, config=config)

    # All feature specs complete
    log("All epic feature specs complete!")
    state["status"] = "completed"
    save_state(state, config)
    log_completion(config, state)
    write_notification(
        config, "execution_complete",
        "Epic complete",
        f"All {len(epic_specs)} feature specs complete for epic {epic_name}",
        severity="info",
    )

    # Complete the epic using the configured strategy
    validation_clean = is_validation_clean(project_dir)
    complete_feature(config, state, validation_clean)


# --- Main ---


def main():
    parser = argparse.ArgumentParser(description="KitTools Execute Orchestrator")
    parser.add_argument(
        "--config", required=True,
        help="Path to .execution-config.json"
    )
    args = parser.parse_args()

    # Register a minimal crash handler before loading config, so that
    # config parse failures still produce a notification.
    _minimal_config = {"project_dir": os.path.dirname(os.path.dirname(args.config))}
    atexit.register(lambda: None)  # placeholder until real handler is set

    try:
        config = load_config(args.config)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        log(f"FATAL: Could not load config: {e}")
        # Try to write a notification even without full config
        try:
            notif_path = os.path.join(_minimal_config["project_dir"], NOTIFICATION_FILE)
            os.makedirs(os.path.dirname(notif_path), exist_ok=True)
            entry = {
                "type": "execution_crashed",
                "title": "Config load failed",
                "details": str(e),
                "severity": "critical",
                "feature": "",
                "timestamp": now_iso(),
            }
            with open(notif_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        sys.exit(1)

    register_crash_handler(config)

    if config.get("epic_specs"):
        run_epic(config)
    else:
        run_single_spec(config)

    log("Orchestrator finished.")


if __name__ == "__main__":
    main()
