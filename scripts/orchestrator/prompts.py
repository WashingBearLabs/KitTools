"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import re

from .sessions import IMPL_RESULT_FILE, VERIFY_RESULT_FILE
from .tests_metrics import detect_related_tests
from .utils import (
    _assert_prompt_fully_substituted,
    log,
    now_iso,
    strip_frontmatter,
)

MAX_PROMPT_CHARS = 480_000
DIFF_CONTENT_MAX = 20_000  # max chars of inline diff for verifier
PERSISTENT_LEARNINGS_FILE = os.path.join("kit_tools", ".execution-learnings.jsonl")
PERSISTENT_LEARNINGS_MAX = 50
PERSISTENT_LEARNINGS_INJECT = 5


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


def classify_failure(
    impl_output: str, verify_output: str | None,
    verdict: dict | None
) -> str:
    """Classify a story failure into a structured type for retry context.

    Returns one of: TIMEOUT_IMPL, TIMEOUT_VERIFY, TEST_FAILURE, VERDICT_FAIL,
    SESSION_ERROR, UNKNOWN.
    """
    # Implementation session timeout
    if impl_output.startswith("SESSION_ERROR:") and "Timed out" in impl_output:
        return "TIMEOUT_IMPL"
    # Implementation session error (non-timeout)
    if impl_output.startswith(("SESSION_ERROR:", "SESSION_ERROR_PERMANENT:")):
        return "SESSION_ERROR"
    # Verification session timeout
    if verify_output and verify_output.startswith("SESSION_ERROR:") and "Timed out" in verify_output:
        return "TIMEOUT_VERIFY"
    # Verification session error (non-timeout)
    if verify_output and verify_output.startswith(("SESSION_ERROR:", "SESSION_ERROR_PERMANENT:")):
        return "SESSION_ERROR"
    # Verdict-based classification
    if verdict and verdict.get("verdict") == "fail":
        # Use structured tests_passed field if available (preferred)
        tests_passed = verdict.get("tests_passed")
        if tests_passed is False:
            return "TEST_FAILURE"
        elif tests_passed is True:
            return "VERDICT_FAIL"
        # tests_passed not set — fall back to UNKNOWN
        return "VERDICT_FAIL"  # Default assumption: criteria not met
    return "UNKNOWN"


def build_retry_context(
    state: dict, story: dict, attempt: int, spec_key: str | None = None
) -> str:
    """Build structured retry context based on failure type.

    Replaces the generic retry context with failure-type-specific guidance.
    """
    if spec_key is not None:
        stories_dict = state.get("specs", {}).get(spec_key, {}).get("stories", {})
    else:
        stories_dict = state.get("stories", {})
    story_state = stories_dict.get(story["id"], {})

    failure_type = story_state.get("failure_type", "UNKNOWN")
    failure = story_state.get("last_failure", "Unknown failure")
    prev_learnings = story_state.get("learnings", [])

    lines = [
        f"**Attempt:** {attempt}",
        f"**Failure type:** {failure_type}",
        "",
    ]

    # Failure-type-specific guidance
    if failure_type == "TIMEOUT_IMPL":
        lines.append("**What to change this attempt:**")
        lines.append("- Prioritize the minimum viable implementation — skip non-critical polish")
        lines.append("- The previous attempt timed out during implementation")
        lines.append("- Focus on getting all acceptance criteria met with minimal code")
    elif failure_type == "TIMEOUT_VERIFY":
        lines.append("**What to change this attempt:**")
        lines.append("- Add explicit test_mapping entries for changed files before committing")
        lines.append("- The previous attempt timed out during test verification")
        lines.append("- Keep changes minimal to reduce verification scope")
    elif failure_type == "TEST_FAILURE":
        lines.append("**What to change this attempt:**")
        lines.append("- Tests failed on the previous attempt — fix the failing code")
        lines.append(f"- Previous failure details: {failure[:500]}")
    elif failure_type == "VERDICT_FAIL":
        lines.append("**What to change this attempt:**")
        lines.append("- Tests passed but acceptance criteria were not fully met")
        lines.append(f"- Verifier feedback: {failure[:500]}")
        # Include per-criterion status if available from verifier
    elif failure_type == "SESSION_ERROR":
        lines.append("**What to change this attempt:**")
        lines.append("- Previous attempt had a session error (likely transient) — retry with the same approach")
    else:
        lines.append("**What to change this attempt:**")
        lines.append("- Failure could not be classified — review the previous attempt diff and retry with a fresh approach")

    if prev_learnings:
        lines.append("")
        lines.append("**Learnings from previous attempts:**")
        for l in prev_learnings:
            lines.append(f"- {l}")

    return "\n".join(lines)


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


def _get_persistent_learnings_path(project_dir: str) -> str:
    """Return absolute path to persistent learnings file."""
    return os.path.join(project_dir, PERSISTENT_LEARNINGS_FILE)


def _read_persistent_learnings(path: str | None) -> list[dict]:
    """Read persistent learnings from JSONL file. Returns list of learning dicts."""
    if not path or not os.path.exists(path):
        return []
    try:
        entries = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries
    except OSError:
        return []


def persist_learnings(project_dir: str, state: dict) -> None:
    """Persist top learnings from current execution to JSONL file.

    Appends up to 10 learnings (most recent stories first), deduplicates by exact text,
    and caps file at PERSISTENT_LEARNINGS_MAX entries. Uses fcntl for file locking.
    """
    import fcntl

    path = _get_persistent_learnings_path(project_dir)

    # Gather all learnings from current run
    all_learnings = []
    stories_sources = {}  # learning text -> (story_id, spec)

    # Support both single and epic state structures
    if "specs" in state:
        for spec_name, spec_data in state.get("specs", {}).items():
            for sid, sdata in spec_data.get("stories", {}).items():
                for learning in sdata.get("learnings", []):
                    if learning and learning not in stories_sources:
                        all_learnings.append(learning)
                        stories_sources[learning] = (sid, spec_name)
    else:
        for sid, sdata in state.get("stories", {}).items():
            for learning in sdata.get("learnings", []):
                if learning and learning not in stories_sources:
                    all_learnings.append(learning)
                    stories_sources[learning] = (sid, state.get("spec", "unknown"))

    if not all_learnings:
        return

    # Take up to 10 most recent (list is in order of story completion)
    new_entries = []
    today = now_iso()[:10]
    for learning_text in all_learnings[-10:]:
        source = stories_sources.get(learning_text, ("unknown", "unknown"))
        new_entries.append({
            "text": learning_text,
            "source": f"{source[0]} ({source[1]})",
            "date": today,
        })

    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        # Lock file for concurrent safety
        fd = os.open(path, os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            f = os.fdopen(fd, "r+")

            # Read existing entries
            existing = []
            f.seek(0)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            # Deduplicate by exact text match
            existing_texts = {e.get("text") for e in existing}
            for entry in new_entries:
                if entry["text"] not in existing_texts:
                    existing.append(entry)
                    existing_texts.add(entry["text"])

            # Cap at max
            if len(existing) > PERSISTENT_LEARNINGS_MAX:
                existing = existing[-PERSISTENT_LEARNINGS_MAX:]

            # Rewrite file
            f.seek(0)
            f.truncate()
            for entry in existing:
                f.write(json.dumps(entry) + "\n")
            f.flush()
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            # fd is closed by fdopen
    except OSError as e:
        log(f"  WARNING: Could not persist learnings: {e}")


def inject_persistent_learnings(project_dir: str, prior_learnings: list[str]) -> list[str]:
    """Add persistent cross-epic learnings to the prior learnings list.

    Injects up to PERSISTENT_LEARNINGS_INJECT entries, labeled with [From prior epic].
    """
    path = _get_persistent_learnings_path(project_dir)
    persistent = _read_persistent_learnings(path)
    if not persistent:
        return prior_learnings

    # Take most recent persistent learnings
    injected = []
    for entry in persistent[-PERSISTENT_LEARNINGS_INJECT:]:
        text = entry.get("text", "")
        if text and text not in prior_learnings:
            injected.append(f"[From prior epic: {entry.get('source', 'unknown')}] {text}")

    return injected + prior_learnings


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

    # Gather learnings from previous stories + persistent cross-epic learnings
    prior_learnings = gather_prior_learnings(state, story["id"], spec_key)
    prior_learnings = inject_persistent_learnings(config["project_dir"], prior_learnings)

    # Build structured retry context based on failure type
    retry_context = ""
    if attempt > 1:
        retry_context = build_retry_context(state, story, attempt, spec_key)

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

    _assert_prompt_fully_substituted(prompt, "build_implementation_prompt")
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

    # Derive targeted test commands from changed files (T0=explicit, T1=heuristic)
    changed_files = [f.strip() for f in files_changed_from_git.split("\n") if f.strip()]
    test_tiers = detect_related_tests(
        changed_files, config["project_dir"], test_command
    )
    t0_cmd = test_tiers["t0"]
    t1_cmd = test_tiers["t1"]

    # Build the test command section with tier awareness
    quiet_note = (
        "Use quiet flags to suppress PASSED lines, but let failure tracebacks flow in full. "
        "Pipe through `| head -200` as a safety net for runaway output."
    )
    if t0_cmd and t1_cmd:
        test_section = (
            f"**T0 — Targeted tests** (explicitly mapped):\n"
            f"Run first: `{t0_cmd}`\n\n"
            f"**T1 — Broader matches** (heuristic, run if T0 passes and session time permits):\n"
            f"Run second: `{t1_cmd}`\n\n"
            f"**Important:** Run T0 first. Only run T1 if T0 passes and you have time remaining. "
            f"Do NOT run the full test suite. {quiet_note}"
        )
    elif t0_cmd:
        test_section = (
            f"**T0 — Targeted tests** (explicitly mapped):\n"
            f"Run: `{t0_cmd}`\n\n"
            f"**Important:** Only run the targeted command above. Do NOT run the full test suite. {quiet_note}"
        )
    elif t1_cmd:
        test_section = (
            f"**T1 — Heuristic matches** (no explicit test_mapping available):\n"
            f"Run: `{t1_cmd}`\n\n"
            f"**Note:** No explicit test_mapping entries found — these are heuristic matches only.\n"
            f"**Important:** Do NOT run the full test suite. {quiet_note}"
        )
    elif test_command:
        test_section = (
            f"No targeted tests could be identified automatically (no test_mapping entries, "
            f"heuristic matching found no matches).\n\n"
            f"**Your task:** Based on the diff and acceptance criteria, identify the specific test "
            f"files relevant to the changed code and run only those. Look at the test directory "
            f"structure, imports, and class/function names to find the right tests.\n\n"
            f"**Do NOT run the full test suite** (`{test_command}`). "
            f"Running the full suite in a large codebase will waste time and may hang.\n\n"
            f"If you truly cannot identify any relevant tests, note that in your verdict and move on. "
            f"The regression check and end-of-epic validation will catch broader failures.\n\n"
            f"{quiet_note}"
        )
    else:
        test_section = "No test command detected — skip test step unless criteria explicitly mention tests."

    if test_command and (t0_cmd or t1_cmd):
        test_section += (
            f"\n\nT2 — Full suite (for feature validation only, do NOT run during story verification): "
            f"`{test_command}`"
        )

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

    _assert_prompt_fully_substituted(prompt, "build_verification_prompt")
    return prompt


