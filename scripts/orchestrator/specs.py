"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone

import yaml

from .utils import log, run_git

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


