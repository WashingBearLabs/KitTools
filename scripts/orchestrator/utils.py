"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
import yaml

EXECUTION_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB — rotate past this
_TEMPLATE_TOKEN_PATTERN = re.compile(r'\{\{([A-Z][A-Z0-9_]+)\}\}')


def rotate_execution_log_if_large(log_path: str, max_bytes: int = EXECUTION_LOG_MAX_BYTES) -> None:
    """Rotate `log_path` to `log_path.1` if the file exceeds `max_bytes`.

    Keeps a single backup — the next rotation overwrites the old `.1`. This is
    a simple size-based rotation; no counting/aging. Unbounded log growth
    across resumed runs is the concern, not fine-grained history.
    """
    try:
        if not os.path.exists(log_path):
            return
        if os.path.getsize(log_path) <= max_bytes:
            return
        backup = log_path + ".1"
        # os.replace overwrites atomically on POSIX
        os.replace(log_path, backup)
    except OSError:
        pass


def _atomic_json_write(path: str, data) -> None:
    """Atomically write JSON to `path`.

    Writes to a temp file in the same directory, fsyncs the file, then
    `os.replace()`s it over the destination. This is atomic on POSIX, so
    a concurrent reader (the supervisor polling `.execution-health.json`,
    the next orchestrator run reading `.execution-state.json`) will either
    see the old contents or the new contents — never a partial write.

    Ensures the parent directory exists. Raises OSError on filesystem
    failures so callers can maintain their existing error-handling
    strategies (fail-loud for state, fail-quiet for best-effort writes).
    """
    # Bare filenames ("state.json") have no directory component; use CWD.
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    # Temp file lives in the same directory so os.replace is atomic
    # (cross-device replace raises OSError).
    fd, tmp = tempfile.mkstemp(prefix=".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Don't leak the temp file on any exit path — including KeyboardInterrupt.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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


def _assert_prompt_fully_substituted(prompt: str, where: str) -> None:
    """Raise if the built prompt still contains `{{TOKEN}}` placeholders.

    For a plugin whose whole value proposition is autonomous execution, silently
    delivering a malformed prompt to an agent is the worst failure mode: the
    agent sees literal `{{STORY_ID}}` and either hallucinates around it or
    produces garbage. This guard turns that into a loud build-time error
    instead, catching typos in `.replace()` calls and template drift.
    """
    leftovers = _TEMPLATE_TOKEN_PATTERN.findall(prompt)
    if leftovers:
        unique = sorted(set(leftovers))
        raise ValueError(
            f"{where}: prompt has unsubstituted tokens after build: {unique}. "
            f"Check for typos in .replace() calls or template additions that "
            f"weren't wired in the builder."
        )


def extract_agent_required_tokens(template: str) -> set[str]:
    """Read `required_tokens` from the agent template's YAML frontmatter.

    Used by prompt builders to sanity-check that every declared token appears
    in the template body — catches upstream drift where an agent template
    declares a token but forgets to reference it. Returns an empty set if the
    field is missing or the frontmatter is malformed.
    """
    stripped = template.lstrip()
    if not stripped.startswith("---"):
        return set()
    end = stripped.find("---", 3)
    if end == -1:
        return set()
    fm_text = stripped[3:end]
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return set()
    if not isinstance(fm, dict):
        return set()
    tokens = fm.get("required_tokens", [])
    if not isinstance(tokens, list):
        return set()
    return {t for t in tokens if isinstance(t, str)}


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


# --- Subprocess helpers (live here to break module import cycles: git_ops,
# --- specs, and supervisor all need run_git, and tmux cleanup is called
# --- from both entry and git_ops; putting these in utils lets every
# --- domain module depend on utils without circular imports.)


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
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


