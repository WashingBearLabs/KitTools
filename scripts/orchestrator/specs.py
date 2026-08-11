"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone

import yaml

from .utils import atomic_write_text, log, run_git


def _split_leading_comments(content: str) -> tuple[str, str]:
    """Split a leading run of HTML comments (+ surrounding whitespace) off
    ``content``. The 2.x templates emit a ``<!-- Template Version: X -->``
    comment (and EPIC.md an additional multi-line ``<!-- Seeding: ... -->``
    block) before the frontmatter delimiter — a match anchored at byte 0 must
    skip this prefix first, or it silently fails on every template-generated
    file (this class of bug hit ``archive_spec`` once already, independently
    of the fix here). Returns ``(prefix, rest)`` such that
    ``prefix + rest == content``.
    """
    m = re.match(r"\A(?:\s*<!--.*?-->)*\s*", content, flags=re.DOTALL)
    prefix_len = m.end() if m else 0
    return content[:prefix_len], content[prefix_len:]


def parse_spec_frontmatter(spec_path: str) -> dict:
    """Parse YAML frontmatter from a feature spec markdown file using PyYAML.

    See :func:`_frontmatter_from_content` for the leading-comment caveat.
    """
    with open(spec_path, "r") as f:
        content = f.read()
    return _frontmatter_from_content(content)


def _frontmatter_from_content(content: str) -> dict:
    """Frontmatter parsing over already-read content.

    The frontmatter block is NOT always on line 1: the 2.x templates emit a
    ``<!-- Template Version: X -->`` comment first (and EPIC.md an additional
    multi-line ``<!-- Seeding: ... -->`` block). Anchoring the match at byte 0
    silently failed for every template-generated spec — returning ``{}`` so the
    ``size:`` hint was ignored and every story ran at the M-size timeout. Skip
    any leading run of HTML comments and blank lines before matching.
    """
    _, body = _split_leading_comments(content)
    match = re.match(r'^---[ \t]*\r?\n(.*?)\r?\n---', body, re.DOTALL)
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


# --- Story execution order ------------------------------------------------
# Through 2.10.x stories executed strictly in document order, so an
# "Execution order: US-004 → US-001 → ..." line an author wrote into a spec —
# the natural thing to write once validation reveals a dependency the ID
# numbering doesn't reflect — was a silent no-op. Now the orchestrator honors
# it: an `execution_order` frontmatter list (authoritative) or an
# "Execution order:" line in the body reorders the story walk; stories not
# listed follow in document order. Physically reordering sections still works.

_US_ID_RE = re.compile(r"\bUS-\d+\b", re.IGNORECASE)
_EXEC_ORDER_LINE_RE = re.compile(
    r"^[ \t]*(?:>[ \t]*)?(?:\*\*)?Execution[ \t]+order(?::\*\*|\*\*:?|:)(?P<rest>.*)$",
    re.MULTILINE | re.IGNORECASE,
)


def _execution_order_ids(content: str) -> list[str]:
    """Declared story execution order for a spec, as a deduped list of IDs.

    Frontmatter ``execution_order`` (list or string) wins; otherwise the first
    "Execution order:" line in the body is used. IDs are extracted permissively
    (any ``US-NNN`` token, in order) so arrow/comma/space separators all work.
    Empty list when nothing is declared — document order applies.
    """
    ids: list[str] = []
    fm = _frontmatter_from_content(content)
    raw = fm.get("execution_order")
    if isinstance(raw, list):
        ids = [i for v in raw for i in _US_ID_RE.findall(str(v))]
    elif isinstance(raw, str):
        ids = _US_ID_RE.findall(raw)
    if not ids:
        m = _EXEC_ORDER_LINE_RE.search(content)
        if m:
            ids = _US_ID_RE.findall(m.group("rest"))
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        i = i.upper()
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _apply_execution_order(stories: list[dict], order: list[str]) -> list[dict]:
    """Reorder ``stories``: listed IDs first (in listed order), the rest in
    document order. IDs that match no story are ignored here — the executor
    surfaces them once via :func:`execution_order_note`."""
    by_id = {s["id"].upper(): s for s in stories}
    ordered = [by_id[i] for i in order if i in by_id]
    listed = {s["id"].upper() for s in ordered}
    ordered.extend(s for s in stories if s["id"].upper() not in listed)
    return ordered


def execution_order_note(spec_path: str) -> str | None:
    """One-line human-readable note about a spec's declared execution order.

    Returns None when the spec declares nothing (document order applies).
    Used by the executor to log the effective order once per spec, so the
    author can see the declaration was read — the failure mode this feature
    replaces was precisely that the line looked authoritative and did nothing.
    """
    try:
        with open(spec_path, "r") as f:
            content = f.read()
    except OSError:
        return None
    order = _execution_order_ids(content)
    if not order:
        return None
    doc_ids = [m.group(1).upper() for m in re.finditer(r"^### (US-\d+):", content, re.MULTILINE)]
    known = [i for i in order if i in set(doc_ids)]
    unknown = [i for i in order if i not in set(doc_ids)]
    unlisted = [i for i in doc_ids if i not in set(known)]
    note = "Story execution order (from spec): " + " -> ".join(known + unlisted)
    if unknown:
        note += f" [WARNING: declared IDs not found in spec, ignored: {', '.join(unknown)}]"
    return note


def parse_stories_from_spec(spec_path: str) -> list[dict]:
    """Parse user stories from a feature spec markdown file.

    Returns a list of dicts with keys: id, title, description, criteria,
    criteria_text — in execution order: the spec's declared ``execution_order``
    (frontmatter or "Execution order:" line) when present, document order
    otherwise.
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

    order = _execution_order_ids(content)
    if order:
        stories = _apply_execution_order(stories, order)
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
    # Atomic: a crash mid-write must not leave a truncated spec — the spec file
    # is both the human-readable record and the orchestrator's story source.
    atomic_write_text(spec_path, content)
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
    # warn-only: the tag may already exist when a crashed run resumes past a
    # previously completed spec — not an error.
    run_git(["tag", tag_name], project_dir, warn=True)
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
    prefix, body = _split_leading_comments(content)
    fm_match = re.match(r'(---[ \t]*\r?\n)(.*?)(---)', body, re.DOTALL)
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
        new_fm = fm_match.group(1) + fm_text + fm_match.group(3)
        content = prefix + new_fm + body[fm_match.end():]

    # Write updated content directly to archive destination
    archive_dir = os.path.join(os.path.dirname(spec_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    dest = os.path.join(archive_dir, os.path.basename(spec_path))
    with open(dest, "w") as f:
        f.write(content)

    # Remove original only after archive write succeeds
    os.remove(spec_path)

    # Stage changes
    # git always reports paths with forward slashes, while os.path.relpath uses
    # os.sep ("\\" on Windows). Normalise here so the verification below can
    # actually match — otherwise the check never succeeds on Windows and every
    # spec archive raises GitRecoveryFailed despite staging correctly.
    rel_dest = os.path.relpath(dest, project_dir).replace(os.sep, "/")
    rel_src = os.path.relpath(spec_path, project_dir).replace(os.sep, "/")
    # warn-only: the staging that actually matters is verified explicitly
    # below (raising GitRecoveryFailed); `rm --cached` on a never-committed
    # spec is a benign "did not match any files".
    run_git(["add", rel_dest], project_dir, warn=True)
    run_git(["rm", "--cached", "-f", rel_src], project_dir, warn=True)

    # Verify-after-mutate: the archived copy MUST be staged, or the completed
    # feature spec silently never reaches the branch/PR — and the subsequent
    # `--allow-empty` completion commit would mask the loss as success. (The file
    # is already on disk, so the dep-gate's filesystem check still passes, but
    # git would not carry the move.) A `git add` of a just-written file only
    # fails on a genuinely broken repo, so treat it as fatal rather than silent.
    staged = run_git(["diff", "--cached", "--name-only"], project_dir)
    staged_paths = {line.strip().replace("\\", "/") for line in staged.stdout.split("\n")}
    if rel_dest not in staged_paths:
        # Deferred import avoids a specs <-> git_ops import cycle (git_ops
        # imports archive_spec from this module).
        from .git_ops import GitRecoveryFailed
        raise GitRecoveryFailed(
            f"Archived spec {rel_dest} could not be staged — the completed "
            f"feature spec would not reach the branch. Inspect: "
            f"cd {project_dir} && git status. "
            f"Staged paths were: {sorted(staged_paths)}"
        )

    log(f"  Archived: {os.path.basename(spec_path)} -> archive/")


