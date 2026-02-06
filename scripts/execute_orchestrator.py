#!/usr/bin/env python3
"""
KitTools Execute Orchestrator

Spawns independent Claude sessions to implement and verify user stories
from a PRD. Manages execution state, retries, and logging.

Launched by the /kit-tools:execute-feature skill for autonomous/guarded modes.

Usage:
    python3 execute_orchestrator.py --config kit_tools/prd/.execution-config.json
"""

import argparse
import json
import os
import re
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


def load_or_create_state(config: dict) -> dict:
    """Read or create .execution-state.json."""
    state_path = get_state_path(config)
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            state = json.load(f)
        # If resuming a completed/failed run, reset status
        if state.get("status") in ("completed", "failed"):
            state["status"] = "running"
        return state

    return {
        "prd": os.path.basename(config["prd_path"]),
        "branch": config["branch_name"],
        "mode": config["mode"],
        "max_retries": config.get("max_retries"),
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "status": "running",
        "stories": {},
        "sessions": {"total": 0, "implementation": 0, "verification": 0},
    }


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
    learnings: list | None = None, failure: str | None = None
) -> None:
    """Update a story's entry in the execution state."""
    entry = state["stories"].get(story_id, {})
    entry["status"] = status
    entry["attempts"] = attempt

    if status == "completed":
        entry["completed_at"] = now_iso()
    if learnings:
        entry.setdefault("learnings", []).extend(learnings)
    if failure:
        entry["last_failure"] = failure

    state["stories"][story_id] = entry


# --- PRD Parsing ---


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


def find_next_uncompleted_story(prd_path: str, state: dict) -> dict | None:
    """Find the first story with uncompleted acceptance criteria."""
    stories = parse_stories_from_prd(prd_path)
    for story in stories:
        # Check PRD checkboxes first (source of truth)
        if story["completed"]:
            continue
        # Cross-reference with state JSON
        story_state = state.get("stories", {}).get(story["id"], {})
        if story_state.get("status") == "completed":
            continue
        return story
    return None


# --- Prompt Building ---


def build_implementation_prompt(
    story: dict, config: dict, state: dict, attempt: int
) -> str:
    """Interpolate the story-implementer template with context."""
    template = config["implementer_template"]
    context = config.get("project_context", {})
    feature_name = config.get("feature_name", "feature")

    # Gather learnings from previous stories
    prior_learnings = []
    for sid, sdata in state.get("stories", {}).items():
        if sid != story["id"]:
            prior_learnings.extend(sdata.get("learnings", []))

    # Build retry context
    retry_context = ""
    if attempt > 1:
        story_state = state.get("stories", {}).get(story["id"], {})
        failure = story_state.get("last_failure", "Unknown failure")
        prev_learnings = story_state.get("learnings", [])
        retry_context = (
            f"This is retry attempt {attempt}.\n\n"
            f"Previous failure:\n{failure}\n\n"
            f"Learnings from previous attempts:\n"
            + "\n".join(f"- {l}" for l in prev_learnings)
        )

    # Prune learnings: summarize if more than 3 stories completed
    if len(prior_learnings) > 15:
        prior_learnings = prior_learnings[-15:]

    # Interpolate template
    prompt = template
    prompt = prompt.replace("{{STORY_ID}}", story["id"])
    prompt = prompt.replace("{{STORY_TITLE}}", story["title"])
    prompt = prompt.replace("{{STORY_DESCRIPTION}}", story["description"])
    prompt = prompt.replace("{{ACCEPTANCE_CRITERIA}}", story["criteria_text"])
    prompt = prompt.replace("{{FEATURE}}", feature_name)
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
    prompt += f"- The PRD file is at: {config['prd_path']}\n"
    prompt += f"- Read the PRD directly for full story context\n"
    prompt += f"- Update PRD checkboxes when criteria are verified\n"
    prompt += f'- Commit with message: feat({feature_name}): {story["id"]} - {story["title"]}\n'
    prompt += f"- Do NOT mark criteria as complete unless you have verified them\n"

    return prompt


def build_verification_prompt(
    story: dict, config: dict, impl_output: str
) -> str:
    """Interpolate the story-verifier template with implementation results."""
    template = config["verifier_template"]
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
    """Extract VERIFICATION_RESULT block from verifier output."""
    match = re.search(
        r"VERIFICATION_RESULT:\s*\n(.+?)END_VERIFICATION_RESULT",
        output, re.DOTALL
    )
    if not match:
        # If no structured output, treat as failure
        return {
            "verdict": "fail",
            "raw_output": output[-2000:],
            "recommendations": "Verifier did not produce structured output. Review manually.",
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
    }


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


def init_execution_log(config: dict) -> None:
    """Create or append a run header to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    feature_name = config.get("feature_name", "unknown")
    mode = config["mode"]
    max_retries = config.get("max_retries", "unlimited")
    prd_name = os.path.basename(config["prd_path"])
    branch = config["branch_name"]
    now = now_iso()

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
    story: dict, attempt: int, config: dict, learnings: list
) -> None:
    """Append a success entry to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    now = now_iso()
    feature_name = config.get("feature_name", "feature")

    entry = f"### {story['id']}: {story['title']} (Attempt {attempt}) — PASS\n"
    entry += f"- Completed: {now}\n"
    entry += f"- Verified by: independent verifier session\n"
    if learnings:
        entry += f"- Learnings: {'; '.join(learnings)}\n"
    entry += f'- Committed: feat({feature_name}): {story["id"]} - {story["title"]}\n'
    entry += "\n"

    with open(log_path, "a") as f:
        f.write(entry)


def log_story_failure(
    story: dict, attempt: int, config: dict, failure_details: str, learnings: list
) -> None:
    """Append a failure entry to EXECUTION_LOG.md."""
    log_path = get_log_path(config)
    now = now_iso()

    entry = f"### {story['id']}: {story['title']} (Attempt {attempt}) — FAIL\n"
    entry += f"- Failed: {now}\n"
    entry += f"- Failure: {failure_details[:500]}\n"
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


def reset_working_tree(project_dir: str) -> None:
    """Reset working tree for retry: git checkout . && git clean -fd"""
    subprocess.run(
        ["git", "checkout", "."],
        cwd=project_dir, capture_output=True
    )
    subprocess.run(
        ["git", "clean", "-fd"],
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


# --- Main Loop ---


def main():
    parser = argparse.ArgumentParser(description="KitTools Execute Orchestrator")
    parser.add_argument(
        "--config", required=True,
        help="Path to .execution-config.json"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    state = load_or_create_state(config)
    save_state(state, config)

    project_dir = config["project_dir"]
    prd_path = config["prd_path"]
    mode = config["mode"]
    max_retries = config.get("max_retries")  # None = unlimited

    log(f"Starting execution: {os.path.basename(prd_path)}")
    log(f"Mode: {mode}, Max retries: {max_retries or 'unlimited'}")
    log(f"Branch: {config['branch_name']}")

    # Initialize execution log
    init_execution_log(config)

    while True:
        # Check pause file between stories
        if pause_file_exists(project_dir):
            wait_for_pause_removal(project_dir)

        # Find next uncompleted story
        story = find_next_uncompleted_story(prd_path, state)
        if not story:
            log("All stories complete!")
            state["status"] = "completed"
            save_state(state, config)
            log_completion(config, state)
            break

        story_state = state.get("stories", {}).get(story["id"], {})
        attempt = story_state.get("attempts", 0)

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
                        failure=f"Exceeded max retries ({max_retries})"
                    )
                    save_state(state, config)
                    sys.exit(1)

            # Reset working tree for retry (attempt > 1)
            if attempt > 1:
                log(f"  Resetting working tree for retry...")
                reset_working_tree(project_dir)

            # --- Implementation session ---
            log(f"Implementing {story['id']}: {story['title']} (attempt {attempt})...")
            update_state_story(state, story["id"], "in_progress", attempt)
            save_state(state, config)

            prompt = build_implementation_prompt(story, config, state, attempt)
            impl_output = run_claude_session(prompt, project_dir)

            state["sessions"]["total"] += 1
            state["sessions"]["implementation"] += 1
            save_state(state, config)

            # Check for session errors
            if impl_output.startswith("SESSION_ERROR:"):
                log(f"  Implementation session error: {impl_output[:200]}")
                learnings = [f"Session error: {impl_output[:200]}"]
                log_story_failure(story, attempt, config, impl_output[:500], learnings)
                update_state_story(state, story["id"], "retrying", attempt, learnings, impl_output[:500])
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
                log_story_success(story, attempt, config, learnings)
                update_state_story(state, story["id"], "completed", attempt, learnings)
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
                    learnings, failure_details
                )
                save_state(state, config)
                # Loop continues to next attempt

    log("Orchestrator finished.")


if __name__ == "__main__":
    main()
