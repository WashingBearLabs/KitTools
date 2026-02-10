#!/usr/bin/env python3
"""
KitTools Execute Orchestrator

Spawns independent Claude sessions to implement and verify user stories
from a PRD. Manages execution state, retries, and logging.

Supports two modes:
- Single-PRD mode: executes stories from one PRD on a feature/[name] branch
- Epic mode: chains multiple PRDs on a shared epic/[name] branch

Launched by the /kit-tools:execute-feature skill for autonomous/guarded modes.

Usage:
    python3 execute_orchestrator.py --config kit_tools/prd/.execution-config.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# --- Constants ---

SESSION_TIMEOUT = 900  # 15 minutes per claude session
PAUSE_POLL_INTERVAL = 10  # seconds between pause file checks
NETWORK_RETRY_WAIT = 30  # seconds between network retries
NETWORK_MAX_RETRIES = 3


# --- State Management ---


def load_config(config_path: str) -> dict:
    """Read .execution-config.json written by the skill."""
    with open(config_path, "r") as f:
        return json.load(f)


def load_or_create_state(config: dict) -> tuple[dict, bool]:
    """Read or create .execution-state.json for single-PRD mode. Returns (state, is_rerun)."""
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
        "prd": os.path.basename(config["prd_path"]),
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
        "current_prd": None,
        "prds": {},
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
    return os.path.join(config["project_dir"], "kit_tools", "prd", ".execution-state.json")


def update_state_story(
    state: dict, story_id: str, status: str, attempt: int,
    learnings: list | None = None, failure: str | None = None,
    prd_key: str | None = None
) -> None:
    """Update a story's entry in the execution state.

    Args:
        prd_key: If set, update state["prds"][prd_key]["stories"][story_id] (epic mode).
                 If None, update state["stories"][story_id] (single-PRD mode).
    """
    if prd_key is not None:
        stories_dict = state["prds"][prd_key].setdefault("stories", {})
    else:
        stories_dict = state.setdefault("stories", {})

    entry = stories_dict.get(story_id, {})
    entry["status"] = status
    entry["attempts"] = attempt

    if status == "completed":
        entry["completed_at"] = now_iso()
    if learnings:
        entry.setdefault("learnings", []).extend(learnings)
    if failure:
        entry["last_failure"] = failure

    stories_dict[story_id] = entry


# --- PRD Parsing ---


def parse_prd_frontmatter(prd_path: str) -> dict:
    """Parse YAML frontmatter from a PRD markdown file."""
    with open(prd_path, "r") as f:
        content = f.read()
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}
    frontmatter = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            if not value:
                continue  # Skip empty values
            if value == '[]':
                frontmatter[key] = []
            elif value.startswith('['):
                frontmatter[key] = [v.strip().strip("'\"") for v in value[1:-1].split(',') if v.strip()]
            elif value.lower() == 'true':
                frontmatter[key] = True
            elif value.lower() == 'false':
                frontmatter[key] = False
            elif value.isdigit():
                frontmatter[key] = int(value)
            else:
                frontmatter[key] = value
    return frontmatter


def parse_stories_from_prd(prd_path: str) -> list[dict]:
    """Parse user stories from a PRD markdown file.

    Returns a list of dicts with keys: id, title, description, criteria, criteria_text
    """
    with open(prd_path, "r") as f:
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
            "criteria": criteria,
            "criteria_text": "\n".join(
                f"- [ ] {c}" for c in criteria
            ),
            "completed": len(unchecked) == 0 and len(checked) > 0,
        })

    return stories


def find_next_uncompleted_story(prd_path: str, stories_state: dict) -> dict | None:
    """Find the first story with uncompleted acceptance criteria.

    Args:
        prd_path: Path to the PRD file.
        stories_state: Dict with a "stories" key mapping story IDs to their state.
                       For single-PRD mode: the top-level state.
                       For epic mode: state["prds"][prd_key].
    """
    stories = parse_stories_from_prd(prd_path)
    for story in stories:
        # Check PRD checkboxes first (source of truth)
        if story["completed"]:
            continue
        # Cross-reference with state JSON
        story_state = stories_state.get("stories", {}).get(story["id"], {})
        if story_state.get("status") == "completed":
            continue
        return story
    return None


# --- Epic Helpers ---


def check_dependencies_archived(project_dir: str, prd_path: str) -> tuple[bool, list[str]]:
    """Check that all depends_on PRDs are archived. Returns (ok, missing_deps)."""
    fm = parse_prd_frontmatter(prd_path)
    deps = fm.get("depends_on", [])
    if not deps:
        return True, []
    archive_dir = os.path.join(project_dir, "kit_tools", "prd", "archive")
    missing = []
    for dep in deps:
        # Check for prd-{dep}.md in archive
        candidates = [f"prd-{dep}.md", f"{dep}.md"]
        found = any(os.path.exists(os.path.join(archive_dir, c)) for c in candidates)
        if not found:
            missing.append(dep)
    return len(missing) == 0, missing


def tag_checkpoint(project_dir: str, epic_name: str, feature_name: str) -> None:
    """Create a git tag marking a PRD checkpoint within an epic."""
    tag_name = f"{epic_name}/{feature_name}-complete"
    subprocess.run(
        ["git", "tag", tag_name],
        cwd=project_dir, capture_output=True
    )
    log(f"  Tagged checkpoint: {tag_name}")


def archive_prd(project_dir: str, prd_path: str, feature_name: str) -> None:
    """Update PRD frontmatter and move to archive directory."""
    # Update frontmatter
    with open(prd_path, "r") as f:
        content = f.read()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = content.replace("status: active", "status: completed")
    content = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {today}", content)
    if "completed:" not in content:
        content = re.sub(
            r"(updated: \d{4}-\d{2}-\d{2})",
            f"\\1\ncompleted: {today}",
            content
        )
    with open(prd_path, "w") as f:
        f.write(content)

    # Move to archive
    archive_dir = os.path.join(os.path.dirname(prd_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    dest = os.path.join(archive_dir, os.path.basename(prd_path))
    shutil.move(prd_path, dest)

    # Stage changes
    rel_dest = os.path.relpath(dest, project_dir)
    rel_src = os.path.relpath(prd_path, project_dir)
    subprocess.run(["git", "add", rel_dest], cwd=project_dir, capture_output=True)
    # Stage the deletion of the old path
    subprocess.run(["git", "rm", "--cached", "-f", rel_src], cwd=project_dir, capture_output=True)

    log(f"  Archived: {os.path.basename(prd_path)} -> archive/")


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


def gather_prior_learnings(state: dict, current_story_id: str, prd_key: str | None = None) -> list[str]:
    """Gather learnings from completed stories.

    In epic mode, also gathers learnings from all completed PRDs.
    """
    prior_learnings = []

    if prd_key is not None:
        # Epic mode: gather from ALL PRDs' stories
        for pk, prd_data in state.get("prds", {}).items():
            for sid, sdata in prd_data.get("stories", {}).items():
                if pk == prd_key and sid == current_story_id:
                    continue  # Skip current story
                prior_learnings.extend(sdata.get("learnings", []))
    else:
        # Single-PRD mode: gather from state["stories"]
        for sid, sdata in state.get("stories", {}).items():
            if sid != current_story_id:
                prior_learnings.extend(sdata.get("learnings", []))

    # Prune learnings: keep only the most recent
    if len(prior_learnings) > 15:
        prior_learnings = prior_learnings[-15:]

    return prior_learnings


def build_implementation_prompt(
    story: dict, config: dict, state: dict, attempt: int,
    feature_name: str | None = None, prd_path: str | None = None,
    prd_key: str | None = None
) -> str:
    """Interpolate the story-implementer template with context.

    Args:
        feature_name: Override for config["feature_name"] (used in epic mode).
        prd_path: Override for config["prd_path"] (used in epic mode).
        prd_key: If set, look up story state in state["prds"][prd_key] (epic mode).
    """
    template = strip_frontmatter(config["implementer_template"])
    context = config.get("project_context", {})
    feat_name = feature_name or config.get("feature_name", "feature")
    prd = prd_path or config.get("prd_path", "")

    # Gather learnings from previous stories
    prior_learnings = gather_prior_learnings(state, story["id"], prd_key)

    # Build retry context
    retry_context = ""
    if attempt > 1:
        if prd_key is not None:
            stories_dict = state.get("prds", {}).get(prd_key, {}).get("stories", {})
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

    # Interpolate template
    prompt = template
    prompt = prompt.replace("{{STORY_ID}}", story["id"])
    prompt = prompt.replace("{{STORY_TITLE}}", story["title"])
    prompt = prompt.replace("{{STORY_DESCRIPTION}}", story["description"])
    prompt = prompt.replace("{{ACCEPTANCE_CRITERIA}}", story["criteria_text"])
    prompt = prompt.replace("{{FEATURE}}", feat_name)
    prompt = prompt.replace("{{PRD_OVERVIEW}}", context.get("prd_overview", "Not available"))
    prompt = prompt.replace("{{PROJECT_SYNOPSIS}}", context.get("synopsis", "Not available"))
    prompt = prompt.replace("{{CODE_ARCH}}", context.get("code_arch", "Not available"))
    prompt = prompt.replace("{{CONVENTIONS}}", context.get("conventions", "Not available"))
    prompt = prompt.replace("{{GOTCHAS}}", context.get("gotchas", "Not available"))
    prompt = prompt.replace(
        "{{PRIOR_LEARNINGS}}",
        "\n".join(f"- {l}" for l in prior_learnings) if prior_learnings else "None yet"
    )
    prompt = prompt.replace("{{RETRY_CONTEXT}}", retry_context or "First attempt — no retry context.")

    # Add autonomous-mode instructions
    prompt += f"\n\n## Additional Instructions (Autonomous Mode)\n"
    prompt += f"- The PRD file is at: {prd}\n"
    prompt += f"- Read the PRD directly for full story context\n"
    prompt += f"- Update PRD checkboxes when criteria are verified\n"
    prompt += f'- Commit with message: feat({feat_name}): {story["id"]} - {story["title"]}\n'
    prompt += f"- Do NOT mark criteria as complete unless you have verified them\n"

    return prompt


def build_verification_prompt(
    story: dict, config: dict, impl_output: str
) -> str:
    """Interpolate the story-verifier template with implementation results."""
    template = strip_frontmatter(config["verifier_template"])
    context = config.get("project_context", {})

    # Parse implementation result for files changed and evidence
    files_changed = extract_section(impl_output, "files_changed:")
    evidence = extract_section(impl_output, "criteria_met:")

    prompt = template
    prompt = prompt.replace("{{STORY_ID}}", story["id"])
    prompt = prompt.replace("{{STORY_TITLE}}", story["title"])
    prompt = prompt.replace("{{ACCEPTANCE_CRITERIA}}", story["criteria_text"])
    prompt = prompt.replace("{{FILES_CHANGED}}", files_changed or "See implementation output below")
    prompt = prompt.replace("{{IMPLEMENTATION_EVIDENCE}}", evidence or impl_output[-3000:])
    prompt = prompt.replace("{{CONVENTIONS}}", context.get("conventions", "Not available"))

    return prompt


def extract_section(text: str, section_header: str) -> str | None:
    """Extract a section from structured output text."""
    start = text.find(section_header)
    if start == -1:
        return None

    # Find the next section header or end marker
    rest = text[start + len(section_header):]
    # Look for next top-level key (word followed by colon at start of line)
    end_match = re.search(r"^\w+:", rest, re.MULTILINE)
    if end_match:
        return rest[:end_match.start()].strip()
    return rest.strip()


# --- Claude Session ---


def run_claude_session(prompt: str, project_dir: str) -> str:
    """Execute a claude -p session and capture output."""
    for network_attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--dangerously-skip-permissions",
                ],
                capture_output=True,
                text=True,
                timeout=SESSION_TIMEOUT,
                cwd=project_dir,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                # Check for network-related errors
                if any(kw in stderr.lower() for kw in ("network", "connection", "timeout", "econnrefused")):
                    if network_attempt < NETWORK_MAX_RETRIES:
                        log(f"  Network error (attempt {network_attempt}/{NETWORK_MAX_RETRIES}), retrying in {NETWORK_RETRY_WAIT}s...")
                        time.sleep(NETWORK_RETRY_WAIT)
                        continue
                # Non-network error or final network retry
                return f"SESSION_ERROR: Exit code {result.returncode}\n{stderr}\n{result.stdout}"

            return result.stdout

        except subprocess.TimeoutExpired:
            return f"SESSION_ERROR: Timed out after {SESSION_TIMEOUT}s"
        except FileNotFoundError:
            return "SESSION_ERROR: 'claude' command not found. Ensure Claude CLI is installed and in PATH."

    return "SESSION_ERROR: All network retries exhausted"


# --- Verification Parsing ---


def parse_verification_result(output: str) -> dict:
    """Extract VERIFICATION_RESULT block from verifier output.

    Handles common LLM output quirks:
    - Markdown code fences wrapping the structured block
    - Whitespace variations in the markers
    - Falls back to scanning for verdict patterns if structured block is missing
    """
    # Strip markdown code fences before searching (LLMs often wrap output in ```)
    cleaned = re.sub(r'```\w*\n?', '', output)

    match = re.search(
        r"VERIFICATION_RESULT:\s*\n(.+?)END_VERIFICATION_RESULT",
        cleaned, re.DOTALL
    )
    if not match:
        # Fallback: scan for verdict patterns outside the structured block
        fallback_verdict = _fallback_verdict_scan(cleaned)
        if fallback_verdict:
            log(f"  [parse] Structured block missing, fallback detected verdict: {fallback_verdict}")
            return {
                "verdict": fallback_verdict,
                "recommendations": "",
                "overall_notes": "Verdict detected via fallback (no structured output block).",
                "parse_method": "fallback",
            }

        # No structured output and no fallback — log raw tail for diagnosis
        raw_tail = output[-1500:] if len(output) > 1500 else output
        log(f"  [parse] No structured output found. Raw output tail ({len(output)} chars total):")
        for line in raw_tail.split('\n')[-10:]:
            log(f"    | {line[:200]}")

        return {
            "verdict": "fail",
            "raw_output": output[-2000:],
            "recommendations": "Verifier did not produce structured output. Review manually.",
            "parse_method": "none",
        }

    block = match.group(1)

    # Extract verdict
    verdict_match = re.search(r"verdict:\s*(\w+)", block)
    verdict = verdict_match.group(1).lower() if verdict_match else "fail"

    # Extract recommendations
    rec_match = re.search(r"recommendations:\s*\"?(.+?)\"?\s*$", block, re.MULTILINE)
    recommendations = rec_match.group(1) if rec_match else ""

    # Extract overall notes
    notes_match = re.search(r"overall_notes:\s*\"?(.+?)\"?\s*$", block, re.MULTILINE)
    overall_notes = notes_match.group(1) if notes_match else ""

    return {
        "verdict": verdict,
        "recommendations": recommendations,
        "overall_notes": overall_notes,
        "raw_block": block,
        "parse_method": "structured",
    }


def _fallback_verdict_scan(text: str) -> str | None:
    """Scan verifier output for verdict patterns when the structured block is missing.

    Returns "pass" or "fail", or None if no pattern is detected.
    """
    # Look for explicit verdict lines anywhere in the output
    verdict_match = re.search(r"verdict:\s*(pass|fail)", text, re.IGNORECASE)
    if verdict_match:
        return verdict_match.group(1).lower()

    # Look for strong pass/fail signals in the last 500 chars (where conclusions tend to be)
    tail = text[-500:].lower()
    pass_signals = [
        "all criteria met", "all criteria verified", "all criteria pass",
        "verification: pass", "overall: pass",
    ]
    fail_signals = [
        "criteria not met", "verification: fail", "overall: fail",
        "criteria failed",
    ]

    has_pass = any(s in tail for s in pass_signals)
    has_fail = any(s in tail for s in fail_signals)

    if has_pass and not has_fail:
        return "pass"
    if has_fail and not has_pass:
        return "fail"

    return None


def extract_combined_learnings(impl_output: str, verify_output: str) -> list[str]:
    """Extract learnings from both implementation and verification outputs."""
    learnings = []

    # From implementation output
    impl_match = re.search(
        r"IMPLEMENTATION_RESULT:.+?learnings:\s*\n(.+?)(?:issues:|END_IMPLEMENTATION_RESULT)",
        impl_output, re.DOTALL
    )
    if impl_match:
        for line in impl_match.group(1).strip().split("\n"):
            line = line.strip().lstrip("- ").strip('"').strip("'")
            if line:
                learnings.append(line)

    # From verification output
    verify_result = parse_verification_result(verify_output)
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
        epic_prds = config["epic_prds"]
        header = f"""
## Run: epic/{epic_name} — {now[:10]}
- **Epic:** {epic_name}
- **Branch:** {branch}
- **Mode:** {mode} ({f'max {max_retries} retries' if max_retries else 'unlimited retries'})
- **PRDs:** {len(epic_prds)} total

"""
    else:
        feature_name = config.get("feature_name", "unknown")
        prd_name = os.path.basename(config["prd_path"])

        # Count total stories
        stories = parse_stories_from_prd(config["prd_path"])
        total = len(stories)
        complete = sum(1 for s in stories if s["completed"])

        header = f"""
## Run: {feature_name} — {now[:10]}
- **PRD:** {prd_name}
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
    # Strip SESSION_ERROR prefix
    if details.startswith("SESSION_ERROR:"):
        details = details[len("SESSION_ERROR:"):].strip()
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

    # Support both single-PRD and epic state structures
    if "prds" in state:
        # Epic mode: aggregate across all PRDs
        total_stories = 0
        completed = 0
        total_attempts = 0
        for prd_data in state.get("prds", {}).values():
            for sdata in prd_data.get("stories", {}).values():
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


def wait_for_pause_removal(project_dir: str) -> None:
    """Poll until the pause file is removed."""
    log("Paused. Remove kit_tools/.pause_execution to resume.")
    while pause_file_exists(project_dir):
        time.sleep(PAUSE_POLL_INTERVAL)
    log("Pause file removed. Resuming execution.")


# --- Git ---


def get_head_commit(project_dir: str) -> str:
    """Get the current HEAD commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_dir, capture_output=True, text=True
    )
    return result.stdout.strip()


def reset_to_commit(project_dir: str, target_hash: str) -> None:
    """Reset branch to a specific commit, preserving tracking files."""
    # Save tracking files before reset
    tracking_files = [
        os.path.join(project_dir, "kit_tools", "EXECUTION_LOG.md"),
        os.path.join(project_dir, "kit_tools", "AUDIT_FINDINGS.md"),
        os.path.join(project_dir, "kit_tools", "SESSION_SCRATCH.md"),
    ]
    saved = {}
    for f in tracking_files:
        if os.path.exists(f):
            with open(f, "r") as fh:
                saved[f] = fh.read()

    # Hard reset to undo any commits made by the implementer
    subprocess.run(
        ["git", "reset", "--hard", target_hash],
        cwd=project_dir, capture_output=True
    )
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=project_dir, capture_output=True
    )

    # Restore tracking files
    for f, content in saved.items():
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh:
            fh.write(content)


def verify_branch_base(project_dir: str) -> bool:
    """Verify the feature branch is based on main."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "main", "HEAD"],
        cwd=project_dir, capture_output=True
    )
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

    subprocess.run(
        ["git", "add"] + files_to_commit,
        cwd=project_dir, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", f"chore({feature_name}): execution log and audit findings"],
        cwd=project_dir, capture_output=True
    )


# --- Utilities ---


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


# --- Story Execution Loop ---


def execute_prd_stories(
    prd_path: str, feature_name: str, config: dict, state: dict,
    prd_key: str | None = None
) -> dict:
    """Execute all stories in a single PRD. Returns updated state.

    Args:
        prd_path: Absolute path to the PRD file.
        feature_name: Feature name for commit messages.
        config: Orchestrator config dict.
        state: Execution state dict.
        prd_key: If set, story state lives under state["prds"][prd_key] (epic mode).
                 If None, story state lives under state["stories"] (single-PRD mode).
    """
    project_dir = config["project_dir"]
    mode = config["mode"]
    max_retries = config.get("max_retries")

    # Determine which stories_state dict to use for find_next_uncompleted_story
    if prd_key is not None:
        stories_state = state["prds"][prd_key]
    else:
        stories_state = state

    while True:
        # Check pause file between stories
        if pause_file_exists(project_dir):
            wait_for_pause_removal(project_dir)

        # Find next uncompleted story
        story = find_next_uncompleted_story(prd_path, stories_state)
        if not story:
            return state  # All stories done

        story_state_entry = stories_state.get("stories", {}).get(story["id"], {})
        attempt = story_state_entry.get("attempts", 0)
        pre_story_hash = get_head_commit(project_dir)

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
                        sys.exit(0)
                    attempt = 1  # Reset for new round
                    continue
                else:
                    log(f"Story {story['id']} exceeded max retries ({max_retries}). Stopping.")
                    state["status"] = "failed"
                    update_state_story(
                        state, story["id"], "failed", attempt - 1,
                        failure=f"Exceeded max retries ({max_retries})",
                        prd_key=prd_key
                    )
                    save_state(state, config)
                    sys.exit(1)

            # Check if this is a verification-only retry (implementation succeeded
            # but verifier output couldn't be parsed). If the HEAD has moved past
            # pre_story_hash, the implementation commit exists — skip re-implementation.
            current_hash = get_head_commit(project_dir)
            verify_only = (
                attempt > 1
                and current_hash != pre_story_hash
                and stories_state.get("stories", {}).get(story["id"], {}).get("last_failure", "")
                    .startswith("Verifier did not produce structured output")
            )

            if attempt > 1 and not verify_only:
                log(f"  Resetting to pre-story state for retry...")
                reset_to_commit(project_dir, pre_story_hash)

            # --- Implementation session (skip if verify-only retry) ---
            if verify_only:
                log(f"Verify-only retry for {story['id']}: {story['title']} (attempt {attempt})...")
                impl_output = ""  # No new implementation output
            else:
                log(f"Implementing {story['id']}: {story['title']} (attempt {attempt})...")
                update_state_story(state, story["id"], "in_progress", attempt, prd_key=prd_key)
                save_state(state, config)

                prompt = build_implementation_prompt(
                    story, config, state, attempt,
                    feature_name=feature_name, prd_path=prd_path, prd_key=prd_key
                )
                impl_output = run_claude_session(prompt, project_dir)

                state["sessions"]["total"] += 1
                state["sessions"]["implementation"] += 1
                save_state(state, config)

                # Check for session errors
                if impl_output.startswith("SESSION_ERROR:"):
                    log(f"  Implementation session error: {impl_output[:200]}")
                    learnings = [f"Session error: {impl_output[:200]}"]
                    log_story_failure(story, attempt, config, impl_output[:500], learnings)
                    update_state_story(
                        state, story["id"], "retrying", attempt, learnings, impl_output[:500],
                        prd_key=prd_key
                    )
                    save_state(state, config)
                    continue

            # --- Verification session ---
            log(f"  Verifying {story['id']}...")
            verify_prompt = build_verification_prompt(story, config, impl_output)
            verify_output = run_claude_session(verify_prompt, project_dir)

            state["sessions"]["total"] += 1
            state["sessions"]["verification"] += 1
            save_state(state, config)

            # Parse verification result
            verdict = parse_verification_result(verify_output)

            if verdict["verdict"] == "pass":
                learnings = extract_combined_learnings(impl_output, verify_output)
                log(f"  {story['id']} PASSED (attempt {attempt})")
                log_story_success(story, attempt, config, learnings, feature_name=feature_name)
                update_state_story(
                    state, story["id"], "completed", attempt, learnings, prd_key=prd_key
                )
                save_state(state, config)
                break  # Move to next story
            else:
                failure_details = verdict.get("recommendations", "Verification failed")
                learnings = extract_combined_learnings(impl_output, verify_output)
                log(f"  {story['id']} FAILED verification (attempt {attempt})")
                log(f"  Reason: {failure_details[:200]}")
                log_story_failure(story, attempt, config, failure_details, learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, failure_details, prd_key=prd_key
                )
                save_state(state, config)
                # Loop continues to next attempt

    return state


# --- Single-PRD Mode ---


def run_single_prd(config: dict) -> None:
    """Execute a single PRD (original behavior, backwards compatible)."""
    state, is_rerun = load_or_create_state(config)
    save_state(state, config)

    project_dir = config["project_dir"]
    prd_path = config["prd_path"]
    mode = config["mode"]
    max_retries = config.get("max_retries")

    log(f"Starting execution: {os.path.basename(prd_path)}")
    log(f"Mode: {mode}, Max retries: {max_retries or 'unlimited'}")
    log(f"Branch: {config['branch_name']}")

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
    execute_prd_stories(prd_path, config.get("feature_name", "feature"), config, state)

    # All stories complete
    log("All stories complete!")

    # Mark completed and log BEFORE spawning validation.
    # validate-feature -> complete-feature will clean up state files,
    # so we must not write to them after the validation session returns.
    state["status"] = "completed"
    save_state(state, config)
    log_completion(config, state)

    # Run feature validation (may auto-invoke complete-feature)
    prd_basename = os.path.basename(prd_path)
    branch = config["branch_name"]
    log("Running feature validation...")
    validate_prompt = (
        f"Run /kit-tools:validate-feature for PRD {prd_basename}. "
        f"Mode: autonomous. Branch: {branch}."
    )
    validate_output = run_claude_session(validate_prompt, project_dir)

    if validate_output.startswith("SESSION_ERROR:"):
        log(f"Validation session error: {validate_output[:200]}")
    else:
        log("Feature validation complete.")

    # Commit tracking files (execution log, audit findings)
    feature_name = config.get("feature_name", "feature")
    commit_tracking_files(project_dir, feature_name)


# --- Epic Mode ---


def run_epic(config: dict) -> None:
    """Execute an epic: multiple PRDs in sequence on a shared branch."""
    state, is_rerun = load_or_create_epic_state(config)
    save_state(state, config)

    project_dir = config["project_dir"]
    epic_name = config["epic_name"]
    epic_prds = config["epic_prds"]

    log(f"Starting epic: {epic_name} ({len(epic_prds)} PRDs)")
    log(f"Branch: {config['branch_name']}")

    if not verify_branch_base(project_dir):
        log(f"WARNING: Branch {config['branch_name']} may not be based on main.")

    # Add re-run separator to execution log if resuming
    if is_rerun:
        log_path = get_log_path(config)
        if os.path.exists(log_path):
            with open(log_path, "a") as f:
                f.write("\n---\n> Previous epic run ended. New run starting below.\n---\n\n")

    init_execution_log(config, epic_mode=True)

    for i, prd_info in enumerate(epic_prds):
        prd_path = prd_info["prd_path"]
        feature_name = prd_info["feature_name"]
        is_final = prd_info.get("epic_final", False)
        prd_basename = os.path.basename(prd_path)

        # Skip already completed PRDs (resume support)
        prd_entry = state["prds"].get(prd_basename, {})
        if prd_entry.get("status") == "completed":
            log(f"Skipping {prd_basename} (already completed)")
            continue

        # Hard gate: verify dependencies are archived
        deps_ok, missing = check_dependencies_archived(project_dir, prd_path)
        if not deps_ok:
            log(f"ERROR: Dependencies not met for {prd_basename}: {missing}")
            log("Cannot continue epic execution.")
            state["status"] = "blocked"
            save_state(state, config)
            sys.exit(1)

        log(f"--- PRD {i+1}/{len(epic_prds)}: {prd_basename} ---")

        # Initialize PRD state entry
        if prd_basename not in state["prds"]:
            state["prds"][prd_basename] = {
                "feature_name": feature_name,
                "status": "in_progress",
                "started_at": now_iso(),
                "stories": {},
            }
        state["current_prd"] = prd_basename
        save_state(state, config)

        # Execute all stories in this PRD
        execute_prd_stories(prd_path, feature_name, config, state, prd_key=prd_basename)

        # PRD stories complete — validate
        log(f"  All stories complete for {prd_basename}. Validating...")
        validate_prompt = (
            f"Run /kit-tools:validate-feature for PRD {prd_basename}. "
            f"Mode: autonomous. Branch: {config['branch_name']}. "
            f"This is part of an epic — do NOT invoke complete-feature."
        )
        validate_output = run_claude_session(validate_prompt, project_dir)
        state["sessions"]["total"] += 1
        state["sessions"]["validation"] += 1

        if validate_output.startswith("SESSION_ERROR:"):
            log(f"  Validation error: {validate_output[:200]}")
            # Continue anyway — validation is informational

        # Commit tracking files for this PRD
        commit_tracking_files(project_dir, feature_name)

        # Tag checkpoint
        tag_checkpoint(project_dir, epic_name, feature_name)

        # Archive PRD
        archive_prd(project_dir, prd_path, feature_name)

        # Commit archive + tag
        subprocess.run(
            ["git", "commit", "-m", f"chore({epic_name}): complete {feature_name}",
             "--allow-empty"],
            cwd=project_dir, capture_output=True
        )

        # Update state
        state["prds"][prd_basename]["status"] = "completed"
        state["prds"][prd_basename]["completed_at"] = now_iso()
        save_state(state, config)

        log(f"  {prd_basename} complete. Tagged: {epic_name}/{feature_name}-complete")

        # Pause between PRDs if configured
        if config.get("epic_pause_between_prds") and not is_final:
            pause_path = os.path.join(project_dir, "kit_tools", ".pause_execution")
            with open(pause_path, "w") as f:
                f.write(f"Epic paused after {prd_basename}. Remove this file to continue.\n")
            log(f"  Pausing between PRDs. Review {prd_basename} results, then:")
            log(f"    rm kit_tools/.pause_execution")
            wait_for_pause_removal(project_dir)

    # All PRDs complete
    log("All epic PRDs complete!")
    state["status"] = "completed"
    save_state(state, config)
    log_completion(config, state)

    # Final: run complete-feature for the epic
    # (This handles PR creation for the epic branch)
    complete_prompt = (
        f"Run /kit-tools:complete-feature for the epic '{epic_name}'. "
        f"Branch: {config['branch_name']}. "
        f"All PRDs are archived. Create a PR for the epic branch."
    )
    complete_output = run_claude_session(complete_prompt, project_dir)

    if complete_output.startswith("SESSION_ERROR:"):
        log(f"Completion session error: {complete_output[:200]}")
    else:
        log("Epic completion done.")


# --- Main ---


def main():
    parser = argparse.ArgumentParser(description="KitTools Execute Orchestrator")
    parser.add_argument(
        "--config", required=True,
        help="Path to .execution-config.json"
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if config.get("epic_prds"):
        run_epic(config)
    else:
        run_single_prd(config)

    log("Orchestrator finished.")


if __name__ == "__main__":
    main()
