"""Execution registry — the cross-worktree pointer store for KitTools.

Part of the KitTools orchestrator package. Added for worktree isolation: once
an epic execution runs inside its own git worktree (rather than the user's live
checkout), a skill invoked from the *main* checkout can no longer find the
execution's state files via cwd. This module is the stable, gitignored pointer
registry that every skill resolves through, regardless of which directory it is
invoked from.

Design decisions (see the worktree-isolation plan):
- **File-per-execution.** Each execution is its own JSON file under
  ``<main_repo>/.kit/executions/<epic>.json``. Two concurrent executions never
  touch the same file, so there is no read-modify-write race on a shared
  registry — the contention problem worktrees exist to solve is not
  reintroduced at the registry layer. No locking required.
- **Main-repo-anchored.** The registry lives in the main worktree only (it is
  gitignored, so it never appears in a linked worktree's checkout). Resolution
  uses ``git rev-parse --git-common-dir`` so any cwd — main or linked worktree —
  finds the same registry.
- **Stdlib-only.** This module deliberately avoids importing the rest of the
  orchestrator package (which pulls in PyYAML and more). Skills invoke it as a
  CLI in the *user's* environment, which may not have PyYAML installed, so the
  registry must work with nothing but the standard library.

This module is also runnable as a script so skills can resolve the registry
without re-implementing git plumbing in bash::

    python3 registry.py resolve-main [dir]
    python3 registry.py project-id [dir]
    python3 registry.py list [dir]
    python3 registry.py get <epic> [dir]
    python3 registry.py worktree-path <epic> [base_root] [dir]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

REGISTRY_DIRNAME = ".kit"
EXECUTIONS_SUBDIR = "executions"
DEFAULT_WORKTREE_HOME = "~/.kit/worktrees"

# Canonical .gitignore block for KitTools' transient runtime state. Single
# source of truth: init-project writes it at setup, and execute-epic re-asserts
# it on the worktree path so a pre-2.6.0 repo (where it's missing) can't commit
# the `.kit/` registry. `.kit/` is the critical line — the rest are transient
# state that simply shouldn't be tracked.
GITIGNORE_MARKER = "# --- KitTools (transient runtime state — do not commit) ---"
GITIGNORE_END = "# --- end KitTools ---"
GITIGNORE_LINES = [
    ".kit/",
    "kit_tools/specs/.execution-config.json",
    "kit_tools/specs/.execution-state.json",
    "kit_tools/specs/.execution-health.json",
    "kit_tools/specs/.execution-control.json",
    "kit_tools/specs/.orchestrator.lock",
    "kit_tools/.pause_execution",
    "kit_tools/.execution-notifications",
    "kit_tools/.execution-events.jsonl",
    "kit_tools/SESSION_SCRATCH.md",
    # Run artifacts (regenerated every run, not source). A *tracked*, mid-run-
    # rewritten EXECUTION_LOG.md was the dirty-tree trigger behind the
    # silent-merge data loss — an inter-story `git checkout` refused because of
    # its uncommitted changes. Ignoring (and untracking) them removes the
    # trigger. ``.md.1`` is the size-based rotation backup.
    "kit_tools/EXECUTION_LOG.md",
    "kit_tools/EXECUTION_LOG.md.1",
    "kit_tools/AUDIT_FINDINGS.md",
    # Supervisor + per-session result artifacts, written by KitTools INSIDE the
    # worktree. The orchestrator has a hard dirty-tree gate, so leaving these
    # unignored makes an enabled `monitor` un-resumable (issue #3) and sweeps
    # them into tracking commits (issue #23).
    "kit_tools/specs/.supervisor.log",
    # Regenerated on every verification by tests_metrics.py (subdir, non-dotfile
    # — must be listed explicitly; the glob below only covers kit_tools/.*).
    "kit_tools/testing/test-metrics.json",
    # Catch-all for the many transient dotfile scratch artifacts written
    # directly under kit_tools/ by the validate-* / sync / seed / vision /
    # orchestrator flows (.validate_impl_*.json, .fm_*, .vi_*, .rx_diff.txt,
    # .fix-result.json, .story-impl-result.json, .execution-learnings.jsonl,
    # .landscape_research.json, .seed_cache, .supervisor_stop, ...). A glob
    # eliminates the drift class entirely: every DURABLE artifact under
    # kit_tools/ (AGENT_README.md, PRODUCT_VISION.md, specs/, arch/, docs/,
    # worktree.yaml) is a non-dotfile, so `.*` can never hide one.
    "kit_tools/.*",
    "!kit_tools/.gitkeep",
]

# Statuses an execution record may carry. Mirrors the orchestrator's own state
# machine (.execution-state.json `status`), plus "paused" for the pause file.
VALID_STATUSES = frozenset(
    {"running", "paused", "completed", "crashed", "blocked"}
)

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


# --- Minimal self-contained helpers (intentionally duplicated from utils to
# --- keep this module stdlib-only; see module docstring). ----------------


def _now_iso() -> str:
    """Current UTC time in the same ISO format the orchestrator state uses."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """Run a git command, capturing output. Never raises on non-zero exit."""
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )


def _atomic_write(path: str, data: dict) -> None:
    """Atomically write ``data`` as JSON to ``path`` (temp file + os.replace).

    Same technique as the orchestrator's ``_atomic_json_write``: a concurrent
    reader sees either the old or the new contents, never a partial write.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _safe_name(name: str) -> str:
    """Sanitise an epic name for use as a filename / path component.

    Collapses any run of characters outside ``[A-Za-z0-9._-]`` to a single
    dash and trims leading/trailing dashes and dots. Returns ``"_"`` for an
    otherwise-empty result so we never produce a hidden or empty filename.
    """
    cleaned = _UNSAFE_NAME.sub("-", name).strip("-.")
    return cleaned or "_"


# --- Main-repo resolution -------------------------------------------------


def find_main_repo(start_dir: str | None = None) -> str | None:
    """Return the absolute path of the *main* worktree's root, from any cwd.

    Works whether ``start_dir`` is the main checkout or a linked worktree.
    ``git rev-parse --git-common-dir`` returns the shared git directory
    (``.git`` for the main repo, an absolute path to the main repo's ``.git``
    when run inside a linked worktree). The main worktree root is that
    directory's parent.

    Returns ``None`` if ``start_dir`` is not inside a git repository.
    """
    start_dir = start_dir or os.getcwd()
    result = _run_git(["rev-parse", "--git-common-dir"], start_dir)
    if result.returncode != 0:
        return None
    common = result.stdout.strip()
    if not common:
        return None
    if not os.path.isabs(common):
        common = os.path.abspath(os.path.join(start_dir, common))
    # The common git dir is "<main_root>/.git"; its parent is the main root.
    # A bare repo has no working tree — guard by checking the basename.
    main_root = os.path.dirname(common)
    return main_root or None


def current_worktree_root(start_dir: str | None = None) -> str | None:
    """Absolute root of the worktree containing ``start_dir`` (may be linked)."""
    start_dir = start_dir or os.getcwd()
    result = _run_git(["rev-parse", "--show-toplevel"], start_dir)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def is_linked_worktree(start_dir: str | None = None) -> bool:
    """True if ``start_dir`` is inside a *linked* worktree (not the main one).

    Used by teardown-capable skills to decide whether they may remove the
    worktree: a skill running *inside* the execution worktree must not try to
    delete its own cwd — it defers removal to a main-side reaper.
    """
    top = current_worktree_root(start_dir)
    main = find_main_repo(start_dir)
    if not top or not main:
        return False
    return os.path.realpath(top) != os.path.realpath(main)


def default_branch(repo: str) -> str:
    """Resolve the repository's integration branch — the thing epics merge into.

    KitTools-initialised repos use ``main`` (init-project creates them that way),
    so this is mostly an identity for them. The detection matters for repos a
    user *imports* that predate the ``main`` default (``master``) or use a custom
    name. Cascade:

    1. The remote's default branch (``origin/HEAD`` → e.g. ``main``) — most
       authoritative when a remote exists.
    2. A local ``main``, then ``master``, if present.
    3. Fall back to ``main`` (a downstream ``git worktree add`` will then fail
       loudly rather than silently target the wrong branch).

    Deliberately does NOT fall back to "current branch" — during an epic the
    user is often on a feature branch, and treating that as the integration
    target would be wrong.
    """
    head = _run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo)
    if head.returncode == 0 and head.stdout.strip():
        ref = head.stdout.strip()
        return ref[len("origin/"):] if ref.startswith("origin/") else ref
    for candidate in ("main", "master"):
        if _run_git(["rev-parse", "--verify", "--quiet",
                     f"refs/heads/{candidate}"], repo).returncode == 0:
            return candidate
    return "main"


def _untrack_ignored(main_repo: str, paths: list[str]) -> list[str]:
    """``git rm --cached`` any of ``paths`` that git is currently tracking.

    Adding a path to ``.gitignore`` does **not** stop git tracking a file that
    is already committed — so a project that ran a pre-2.6.4 KitTools (which
    *committed* EXECUTION_LOG.md / AUDIT_FINDINGS.md) would keep the tracked,
    mid-run-rewritten log that triggers the silent-merge dirty-tree failure.
    This untracks them so the new ignore actually takes effect, without touching
    the working tree (``--cached`` leaves the file on disk). Every entry here is
    transient KitTools state that should never have been tracked, so untracking
    is always the correct migration. Best-effort and a no-op outside a git repo.

    Returns the paths actually untracked.
    """
    untracked: list[str] = []
    for p in paths:
        # `ls-files --error-unmatch` exits non-zero when the path isn't tracked
        # (and when this isn't a git repo) — the cheap, safe "is it tracked?"
        # probe. Directory entries (e.g. ".kit/") never match a file here and
        # are skipped, which is fine: the critical migration targets are files.
        tracked = _run_git(["ls-files", "--error-unmatch", p], main_repo)
        if tracked.returncode != 0:
            continue
        rm = _run_git(["rm", "--cached", "-r", "--quiet", p], main_repo)
        if rm.returncode == 0:
            untracked.append(p)
    return untracked


def ensure_gitignore(main_repo: str) -> dict:
    """Idempotently ensure KitTools' transient-state entries are gitignored.

    Appends any of ``GITIGNORE_LINES`` not already present (matched line-exactly
    anywhere in the file) under a marker block, creating ``.gitignore`` if
    needed. This is the retrofit/safety path for pre-2.6.0 repos where ``.kit/``
    isn't ignored — committing the registry would be a contamination footgun.

    Also untracks (``git rm --cached``) any now-ignored path git is still
    tracking, so the ignore takes effect for projects that committed these files
    under an older KitTools. The working tree is never touched.

    Returns ``{"modified": bool, "added": [lines], "untracked": [paths]}``.
    """
    path = os.path.join(main_repo, ".gitignore")
    existing = ""
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                existing = f.read()
        except OSError:
            return {"modified": False, "added": [], "untracked": []}
    present = {line.strip() for line in existing.splitlines()}
    missing = [line for line in GITIGNORE_LINES if line not in present]
    # Untrack on every call (not only when .gitignore changed): a file can be
    # both already-listed *and* still-tracked if it predates the ignore line.
    untracked = _untrack_ignored(main_repo, GITIGNORE_LINES)
    if not missing:
        return {"modified": bool(untracked), "added": [], "untracked": untracked}
    block = "\n".join([GITIGNORE_MARKER, *missing, GITIGNORE_END])
    prefix = "" if existing.endswith("\n") or not existing else "\n"
    try:
        with open(path, "a") as f:
            f.write(f"{prefix}{block}\n")
    except OSError:
        return {"modified": bool(untracked), "added": [], "untracked": untracked}
    return {"modified": True, "added": missing, "untracked": untracked}


def registry_dir(main_repo: str) -> str:
    """Path to the executions directory under the main repo's ``.kit/``."""
    return os.path.join(main_repo, REGISTRY_DIRNAME, EXECUTIONS_SUBDIR)


def execution_file(main_repo: str, epic: str) -> str:
    """Path to a single execution's registry file."""
    return os.path.join(registry_dir(main_repo), f"{_safe_name(epic)}.json")


# --- Project identity & worktree paths ------------------------------------


def derive_project_id(main_repo: str) -> str:
    """Return a stable, collision-resistant id for this project.

    Format: ``<basename>-<8-hex>``. The hash is derived from the project's
    ``origin`` remote URL when available (normalised so ``git@host:org/repo``
    and ``https://host/org/repo.git`` collapse to the same key), falling back
    to the absolute path of the main repo. This prevents two repositories that
    happen to share a directory basename (e.g. work and personal ``api``) from
    colliding under ``~/.kit/worktrees/``.
    """
    origin = get_normalised_origin(main_repo)
    key = origin if origin is not None else os.path.abspath(main_repo)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    basename = _safe_name(os.path.basename(os.path.abspath(main_repo)))
    return f"{basename}-{digest}"


def _normalise_remote(url: str) -> str:
    """Normalise a git remote URL so equivalent forms hash identically."""
    u = url.strip().lower()
    # scp-style: git@github.com:org/repo(.git) -> github.com/org/repo
    scp = re.match(r"^[^@]+@([^:]+):(.+)$", u)
    if scp:
        u = f"{scp.group(1)}/{scp.group(2)}"
    else:
        u = re.sub(r"^[a-z]+://", "", u)  # strip scheme
        u = re.sub(r"^[^@/]+@", "", u)    # strip userinfo
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[: -len(".git")]
    return u


def get_normalised_origin(project_dir: str) -> str | None:
    """Return the project's normalised `origin` remote URL, or None if there
    isn't one. Same normalisation `derive_project_id` uses (so the two stay
    consistent) but returns None instead of falling back to a local path —
    "no origin" is itself meaningful provenance for a trace record, not
    something to paper over."""
    remote = _run_git(["remote", "get-url", "origin"], project_dir)
    if remote.returncode == 0 and remote.stdout.strip():
        return _normalise_remote(remote.stdout.strip())
    return None


def default_worktree_base(project_id: str) -> str:
    """Default per-project worktree home: ``~/.kit/worktrees/<project_id>``."""
    return os.path.join(os.path.expanduser(DEFAULT_WORKTREE_HOME), project_id)


def compute_worktree_path(base_root: str, epic: str) -> str:
    """Absolute path for an epic's worktree: ``<base_root>/<epic>``.

    ``base_root`` is expanded (``~``) and made absolute so callers can pass a
    contract-configured root verbatim.
    """
    base = os.path.abspath(os.path.expanduser(base_root))
    return os.path.join(base, _safe_name(epic))


# --- Registry CRUD --------------------------------------------------------


def register(main_repo: str, record: dict) -> str:
    """Write (or overwrite) an execution record. Returns the file path.

    ``record`` must contain at least ``epic``. ``started_at`` is stamped on
    first write only; ``updated_at`` is always refreshed.
    """
    epic = record.get("epic")
    if not epic:
        raise ValueError("execution record requires an 'epic' field")
    path = execution_file(main_repo, epic)
    existing = get(main_repo, epic)
    merged = dict(existing or {})
    merged.update(record)
    merged.setdefault("started_at", _now_iso())
    merged["updated_at"] = _now_iso()
    _atomic_write(path, merged)
    return path


def get(main_repo: str, epic: str) -> dict | None:
    """Read a single execution record, or ``None`` if absent/unreadable."""
    path = execution_file(main_repo, epic)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_all(main_repo: str) -> list[dict]:
    """Return every execution record in the registry (skips unreadable ones)."""
    d = registry_dir(main_repo)
    if not os.path.isdir(d):
        return []
    records = []
    for name in sorted(os.listdir(d)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), "r") as f:
                records.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def set_status(main_repo: str, epic: str, status: str) -> bool:
    """Update an execution's ``status``. Returns False if no record exists.

    Unknown status strings are accepted but flagged on stderr — the registry
    should never block an orchestrator from recording state, but a typo is
    worth surfacing.
    """
    record = get(main_repo, epic)
    if record is None:
        return False
    if status not in VALID_STATUSES:
        print(
            f"registry: warning: unknown status {status!r} for epic {epic!r}",
            file=sys.stderr,
        )
    record["status"] = status
    record["updated_at"] = _now_iso()
    _atomic_write(execution_file(main_repo, epic), record)
    return True


def set_status_by_worktree(main_repo: str, worktree_path: str, status: str) -> bool:
    """Update the status of whichever execution owns ``worktree_path``.

    Reconciliation fallback for completion: the orchestrator unambiguously knows
    its own worktree (``project_dir``), but the registry *key* is the epic/feature
    name — and if those ever diverge, a key-based ``set_status`` silently no-ops,
    leaving the record stuck at ``running`` after the state file is cleaned up.
    Matching by worktree path can't diverge. Returns True if a record matched.
    """
    target = os.path.realpath(worktree_path)
    for record in list_all(main_repo):
        wt = record.get("worktree")
        if wt and os.path.realpath(wt) == target:
            return set_status(main_repo, record["epic"], status)
    return False


def reconcile_status(main_repo: str, status: str, *, key: str | None = None,
                     worktree: str | None = None) -> bool:
    """Set an execution's status, preferring the key but falling back to the
    worktree path so a key/epic-name divergence can't strand the record.

    The single robust entry point used by both the orchestrator's completion
    path and its crash handler. Returns True if a record was updated.
    """
    if key and set_status(main_repo, key, status):
        return True
    if worktree and set_status_by_worktree(main_repo, worktree, status):
        return True
    return False


def deregister(main_repo: str, epic: str) -> bool:
    """Delete an execution's registry file. Returns True if a file was removed."""
    path = execution_file(main_repo, epic)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _branch_merged_into_main(main_repo: str, branch: str | None) -> bool | None:
    """True if ``branch`` is fully merged into the integration branch (its tip is
    an ancestor).

    Returns ``None`` if the branch doesn't exist locally (can't tell). Uses
    ``default_branch()`` so imported ``master``-based repos reconcile correctly.
    """
    if not branch:
        return None
    exists = _run_git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
                      main_repo)
    if exists.returncode != 0:
        return None
    base = default_branch(main_repo)
    r = _run_git(["merge-base", "--is-ancestor", branch, base], main_repo)
    return r.returncode == 0


def _worktree_dirty(worktree_path: str | None) -> bool:
    """True if the worktree has uncommitted or untracked (non-ignored) changes."""
    if not worktree_path or not os.path.isdir(worktree_path):
        return False
    r = _run_git(["status", "--porcelain"], worktree_path)
    return bool(r.stdout.strip())


def _read_state_progress(worktree_path: str | None) -> tuple[str | None, str | None]:
    """Read live ``status``/``updated_at`` from the worktree's execution state.

    The registry record's own ``updated_at`` is frozen at registration; the
    orchestrator advances its `.execution-state.json` instead. Surfacing the
    state file's timestamp keeps raw census output from *looking* stale even
    though the live signals (``tmux_alive``, ``disposition``) are already
    correct. Returns ``(None, None)`` if the state file is absent/unreadable.
    """
    if not worktree_path:
        return (None, None)
    path = os.path.join(worktree_path, "kit_tools", "specs", ".execution-state.json")
    try:
        with open(path, "r") as f:
            state = json.load(f)
        return (state.get("status"), state.get("updated_at"))
    except (OSError, json.JSONDecodeError):
        return (None, None)


def _tmux_alive(session: str | None) -> bool:
    """Best-effort: True if a tmux session named ``session`` is running."""
    if not session:
        return False
    try:
        r = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def census(main_repo: str) -> list[dict]:
    """Enrich every registry record with reconciliation signals + a suggested
    disposition, for `start-session` / `close-session` / `execution-status`.

    Each returned dict is the stored record plus:
    - ``worktree_exists`` — the worktree directory is still present
    - ``worktree_dirty`` — has uncommitted/untracked work
    - ``branch_merged`` — branch is fully merged into main (None if branch gone)
    - ``tmux_alive`` — the orchestrator's tmux session is running
    - ``disposition`` — one of:
        - ``active``   — tmux alive; an execution is live, do not touch
        - ``orphan``   — worktree directory is gone; registry entry is stale
        - ``reapable`` — finished, clean, merged-or-completed → safe to teardown
        - ``flag``     — needs attention (dirty, unmerged, or crashed); keep + surface

    These are advisory. The actual `teardown()` always re-checks via git's own
    guards, so a stale-by-a-moment census can never cause data loss.
    """
    out: list[dict] = []
    for record in list_all(main_repo):
        worktree_path = record.get("worktree")
        branch = record.get("branch")
        exists = bool(worktree_path and os.path.isdir(worktree_path))
        merged = _branch_merged_into_main(main_repo, branch)
        dirty = _worktree_dirty(worktree_path) if exists else False
        alive = _tmux_alive(record.get("tmux"))

        if alive:
            disposition = "active"
        elif not exists:
            disposition = "orphan"
        elif dirty:
            disposition = "flag"
        elif merged or record.get("status") == "completed":
            disposition = "reapable"
        else:
            disposition = "flag"

        state_status, state_updated_at = _read_state_progress(worktree_path)

        enriched = dict(record)
        enriched.update({
            "worktree_exists": exists,
            "worktree_dirty": dirty,
            "branch_merged": merged,
            "tmux_alive": alive,
            "disposition": disposition,
            # Live progress from the worktree's state file (the registry record's
            # own updated_at is frozen at registration).
            "state_status": state_status,
            "state_updated_at": state_updated_at,
        })
        out.append(enriched)
    return out


def _add_worktree_git(main_repo: str, worktree_path: str, branch: str,
                      base: str = "main") -> tuple[bool, str]:
    """`git worktree add` — creates ``branch`` from ``base`` if it doesn't exist
    yet, otherwise attaches to the existing branch (resume). Returns
    ``(ok, message)``.
    """
    parent = os.path.dirname(worktree_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    exists = _run_git(
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], main_repo
    ).returncode == 0
    if exists:
        args = ["worktree", "add", worktree_path, branch]
    else:
        args = ["worktree", "add", worktree_path, "-b", branch, base]
    r = _run_git(args, main_repo)
    return (r.returncode == 0, (r.stderr.strip() or r.stdout.strip()))


def _provision_secret(main_repo: str, worktree_path: str, rel: str) -> str:
    """Make a gitignored secret file available in the worktree.

    Prefers a symlink (no secret duplicated at rest); falls back to a copy only
    where symlinks are unavailable (e.g. unprivileged Windows). Returns the
    method used: ``"symlink"``, ``"copy"``, or ``"skip"`` (source missing/failed).
    """
    src = os.path.join(main_repo, rel)
    dst = os.path.join(worktree_path, rel)
    if not os.path.exists(src):
        return "skip"
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        if os.path.islink(dst) or os.path.exists(dst):
            os.remove(dst)
    except OSError:
        pass
    try:
        os.symlink(os.path.abspath(src), dst)
        return "symlink"
    except (OSError, NotImplementedError):
        try:
            shutil.copy2(src, dst)
            return "copy"
        except OSError:
            return "skip"


def _provision_path_link(main_repo: str, worktree_path: str, rel: str) -> str:
    """Symlink a path (typically a sibling repo / directory) into the worktree's
    namespace.

    Source is resolved from ``main_repo`` and destination from ``worktree_path``
    using the *same* relative path, so ``../Roots`` links the main checkout's
    sibling to the worktree's sibling — portable across machines, no absolute
    path baked into the committed contract. Always a symlink (never copy a whole
    directory). Idempotent: an existing correct symlink is left as-is; a real
    file/dir already at the destination is not clobbered.

    Returns ``"linked"``, ``"exists"`` (already present / correct), or ``"skip"``
    (source missing or symlink failed). Note the destination may live *outside*
    ``worktree_path`` (a sibling) — that's intentional and shared across a
    project's epics; teardown leaves those in place.
    """
    src = os.path.normpath(os.path.join(main_repo, rel))
    dst = os.path.normpath(os.path.join(worktree_path, rel))
    if not os.path.exists(src):
        return "skip"
    if os.path.islink(dst):
        try:
            if os.path.realpath(dst) == os.path.realpath(src):
                return "exists"
        except OSError:
            pass
        try:
            os.remove(dst)
        except OSError:
            pass
    elif os.path.exists(dst):
        return "exists"  # a real file/dir is already there — don't clobber
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        os.symlink(os.path.abspath(src), dst)
        return "linked"
    except (OSError, NotImplementedError):
        return "skip"


def provision_worktree(main_repo: str, key: str, branch: str, *,
                       base: str | None = None, root: str | None = None,
                       env_link: list[str] | None = None,
                       path_links: list[str] | None = None,
                       tmux: str | None = None, mode: str | None = None) -> dict:
    """Create and register an isolated execution worktree.

    This is the **deterministic git/registry mechanics** of launching a
    worktree-isolated execution, consolidated into one tested call so the skill
    doesn't have to orchestrate it through stateful shell steps. It deliberately
    does **not** run ``env_bootstrap``: those commands are project-/language-
    specific (the agnostic part), must be echoed and confirmed first, and stay
    visible in the skill. The skill calls this, then runs the confirmed
    bootstrap commands in the returned worktree.

    Returns a result dict: ``worktree``, ``branch``, ``created`` (bool),
    ``linked`` / ``copied`` / ``skipped`` (secret files by method), ``registered``
    (bool), and ``messages``.
    """
    env_link = env_link or []
    path_links = path_links or []
    base = base or default_branch(main_repo)
    base_root = root or default_worktree_base(derive_project_id(main_repo))
    worktree_path = compute_worktree_path(base_root, key)
    result = {
        "epic": key, "branch": branch, "worktree": worktree_path,
        "main_repo": main_repo, "created": False,
        "linked": [], "copied": [], "skipped": [],
        "path_linked": [], "path_skipped": [],
        "registered": False, "messages": [],
    }

    ok, message = _add_worktree_git(main_repo, worktree_path, branch, base)
    if not ok:
        result["messages"].append(f"git worktree add failed: {message}")
        return result
    result["created"] = True

    for rel in env_link:
        method = _provision_secret(main_repo, worktree_path, rel)
        if method == "symlink":
            result["linked"].append(rel)
        elif method == "copy":
            result["copied"].append(rel)
        else:
            result["skipped"].append(rel)
            result["messages"].append(f"env_link source not found, skipped: {rel}")

    for rel in path_links:
        status = _provision_path_link(main_repo, worktree_path, rel)
        if status in ("linked", "exists"):
            result["path_linked"].append(rel)
        else:
            result["path_skipped"].append(rel)
            result["messages"].append(
                f"path_link source not found in main checkout's namespace, "
                f"skipped: {rel}"
            )

    record = {
        "epic": key, "branch": branch, "worktree": worktree_path,
        "main_repo": main_repo, "status": "running",
        "env_link": list(env_link), "path_links": list(path_links),
    }
    if tmux:
        record["tmux"] = tmux
    if mode:
        record["mode"] = mode
    register(main_repo, record)
    result["registered"] = True
    return result


def scrub_secret_copies(main_repo: str, epic: str) -> list[str]:
    """Remove *copied* (non-symlink) secret files from a kept worktree.

    `env_link` secrets are symlinked by default — a symlink holds no secret at
    rest, so it is skipped (and left intact, since an active debug session may
    rely on it). The copy fallback (Windows / filesystems without symlink
    support) duplicates the secret *into* the worktree, outside the repo's
    gitignore protection. When a worktree is kept rather than removed (teardown
    refused, or a session-close "flag"), those copies should be scrubbed so a
    real secret never lingers in `~/.kit/worktrees/`.

    Reads the configured `env_link` list from the registry record (plain
    strings — no YAML needed here). Returns the relative paths actually removed.
    On a removed/torn-down worktree this is a no-op (the directory is gone).
    """
    record = get(main_repo, epic)
    if record is None:
        return []
    worktree_path = record.get("worktree")
    env_link = record.get("env_link") or []
    if not worktree_path or not os.path.isdir(worktree_path):
        return []
    removed: list[str] = []
    for rel in env_link:
        target = os.path.join(worktree_path, rel)
        try:
            if os.path.islink(target):
                continue  # symlink — no secret content at rest
            if os.path.isfile(target):
                os.remove(target)
                removed.append(rel)
        except OSError:
            continue
    return removed


def teardown(main_repo: str, epic: str, *, force: bool = False,
             delete_branch: bool = True) -> dict:
    """Tear down a finished execution: remove its worktree, delete the (merged)
    branch, prune, and deregister. **Must be called from the main checkout**, not
    from inside the worktree being removed.

    Safety is delegated to git's own guards rather than re-implemented:
    - ``git worktree remove`` (no ``--force``) refuses a worktree with
      uncommitted/untracked work — so dirty trees are *kept and flagged*, never
      silently destroyed. ``force=True`` overrides (explicit human say-so only).
    - ``git branch -d`` (lowercase) refuses an unmerged branch — so a branch with
      work not yet on main is *kept and flagged*, never lost.

    Returns a result dict: ``removed_worktree``, ``deleted_branch``,
    ``deregistered`` (bools), ``kept`` (True if the worktree was refused and
    everything was left intact), and ``messages`` (human-facing notes).
    """
    result = {
        "epic": epic, "removed_worktree": False, "deleted_branch": False,
        "deregistered": False, "kept": False, "messages": [],
    }
    record = get(main_repo, epic)
    if record is None:
        result["messages"].append(f"no execution record for {epic!r}")
        return result

    worktree_path = record.get("worktree")
    branch = record.get("branch")

    if worktree_path and os.path.exists(worktree_path):
        if os.path.realpath(worktree_path) == os.path.realpath(main_repo):
            result["kept"] = True
            result["messages"].append(
                "refusing to remove the main checkout (worktree path == main_repo)"
            )
            return result
        args = ["worktree", "remove"] + (["--force"] if force else []) + [worktree_path]
        r = _run_git(args, main_repo)
        if r.returncode == 0:
            result["removed_worktree"] = True
        else:
            # Dirty/untracked work present — keep everything, flag it, do not
            # delete the branch or deregister. The tree stays accounted for.
            # But scrub any copied secrets: the tree is sticking around, so a
            # copied .env (Windows fallback) shouldn't linger outside gitignore.
            result["kept"] = True
            scrubbed = scrub_secret_copies(main_repo, epic)
            if scrubbed:
                result["scrubbed_secret_copies"] = scrubbed
                result["messages"].append(
                    f"removed copied secret files from kept worktree: {', '.join(scrubbed)}"
                )
            result["messages"].append(
                "worktree not removed (uncommitted or untracked changes — save "
                f"them, then retry; force only when sure): {r.stderr.strip()[:200]}"
            )
            return result
    elif worktree_path:
        result["messages"].append("worktree directory already absent")

    if delete_branch and branch:
        r = _run_git(["branch", "-d", branch], main_repo)
        if r.returncode == 0:
            result["deleted_branch"] = True
        else:
            result["messages"].append(
                f"branch {branch!r} not deleted — unmerged work left for review "
                f"(use `git branch -D` to force): {r.stderr.strip()[:200]}"
            )

    _run_git(["worktree", "prune"], main_repo)

    # Sweep any leaked per-attempt branches (`<branch>-<story>-attempt-<n>`) left
    # by a crashed run — these are disposable working branches, force-deletable.
    if branch:
        swept = []
        listing = _run_git(["branch", "--list", f"{branch}-*-attempt-*"], main_repo)
        if listing.returncode == 0 and listing.stdout.strip():
            for line in listing.stdout.strip().splitlines():
                name = line.strip().lstrip("* ").strip()
                if name and _run_git(["branch", "-D", name], main_repo).returncode == 0:
                    swept.append(name)
        if swept:
            result["swept_attempt_branches"] = swept

    # path_links (e.g. a sibling `../Roots`) typically live *outside* the
    # worktree subdir, at the project's shared worktree root — `git worktree
    # remove` doesn't touch them, and other epics of this project may still rely
    # on them. Leave them in place; just report so they're not a silent orphan.
    left = record.get("path_links") or []
    if left:
        result["left_path_links"] = left
        result["messages"].append(
            "left shared path-link(s) in place (used by other epics of this "
            f"project; remove manually if this was the last): {', '.join(left)}"
        )

    result["deregistered"] = deregister(main_repo, epic)

    # Account for the *project* worktree root (the parent that holds per-epic
    # worktrees and any shared path-link symlinks). After this teardown, if no
    # other execution lives under it, surface it: an empty root is removed; a
    # root still holding shared links is reported (not deleted — a future run of
    # this project reuses them, and a manual symlink shouldn't be nuked).
    if worktree_path:
        base_root = os.path.dirname(os.path.abspath(worktree_path))
        if os.path.isdir(base_root):
            remaining = [
                r for r in list_all(main_repo)
                if r.get("worktree") and os.path.realpath(
                    os.path.dirname(r["worktree"])) == os.path.realpath(base_root)
            ]
            if not remaining:
                leftovers = sorted(os.listdir(base_root))
                if not leftovers:
                    try:
                        os.rmdir(base_root)
                        result["messages"].append(
                            f"removed empty project worktree root {base_root}")
                    except OSError:
                        pass
                else:
                    result["project_root_orphaned"] = base_root
                    result["messages"].append(
                        f"no active executions remain under {base_root} — it "
                        f"holds shared artifacts reused by future runs of this "
                        f"project ({', '.join(leftovers)}); remove it manually if "
                        f"you're done with the project")

    return result


# --- CLI ------------------------------------------------------------------


def _cli(argv: list[str]) -> int:
    """Thin CLI so skills can resolve the registry without bash git plumbing."""
    if not argv:
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]

    def _main_from(args: list[str], idx: int) -> str | None:
        start = args[idx] if len(args) > idx else None
        return find_main_repo(start)

    if cmd == "resolve-main":
        main = _main_from(rest, 0)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        print(main)
        return 0

    if cmd == "project-id":
        main = _main_from(rest, 0)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        print(derive_project_id(main))
        return 0

    if cmd == "list":
        main = _main_from(rest, 0)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        print(json.dumps(list_all(main), indent=2))
        return 0

    if cmd == "census":
        main = _main_from(rest, 0)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        print(json.dumps(census(main), indent=2))
        return 0

    if cmd == "get":
        if not rest:
            print("usage: registry.py get <epic> [dir]", file=sys.stderr)
            return 2
        main = _main_from(rest, 1)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        record = get(main, rest[0])
        print(json.dumps(record, indent=2) if record else "")
        return 0 if record else 1

    if cmd == "set-status":
        # set-status <epic> <status> [dir]
        if len(rest) < 2:
            print("usage: registry.py set-status <epic> <status> [dir]",
                  file=sys.stderr)
            return 2
        main = _main_from(rest, 2)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        ok = set_status(main, rest[0], rest[1])
        if not ok:
            print(f"no execution record for {rest[0]!r}", file=sys.stderr)
            return 1
        return 0

    if cmd == "deregister":
        # deregister <epic> [dir]
        if not rest:
            print("usage: registry.py deregister <epic> [dir]", file=sys.stderr)
            return 2
        main = _main_from(rest, 1)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        deregister(main, rest[0])
        return 0

    if cmd == "provision-worktree":
        import argparse
        p = argparse.ArgumentParser(prog="registry.py provision-worktree",
                                    add_help=False)
        p.add_argument("key")
        p.add_argument("--branch", required=True)
        p.add_argument("--base", default="main")
        p.add_argument("--root", default=None)
        p.add_argument("--tmux", default=None)
        p.add_argument("--mode", default=None)
        p.add_argument("--link", action="append", default=[])
        p.add_argument("--link-path", action="append", default=[])
        p.add_argument("--dir", default=None)
        try:
            ns = p.parse_args(rest)
        except SystemExit:
            return 2
        main = find_main_repo(ns.dir)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        res = provision_worktree(
            main, ns.key, ns.branch, base=ns.base, root=ns.root or None,
            env_link=ns.link, path_links=getattr(ns, "link_path"),
            tmux=ns.tmux, mode=ns.mode,
        )
        print(json.dumps(res, indent=2))
        return 0 if res["created"] else 1

    if cmd == "scrub-secrets":
        # scrub-secrets <epic> [dir]
        if not rest:
            print("usage: registry.py scrub-secrets <epic> [dir]", file=sys.stderr)
            return 2
        main = _main_from(rest, 1)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        removed = scrub_secret_copies(main, rest[0])
        print(json.dumps(removed, indent=2))
        return 0

    if cmd == "ensure-gitignore":
        main = _main_from(rest, 0)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        print(json.dumps(ensure_gitignore(main), indent=2))
        return 0

    if cmd == "is-worktree":
        # Exit 0 if invoked from inside a linked worktree, 1 otherwise.
        start = rest[0] if rest else None
        return 0 if is_linked_worktree(start) else 1

    if cmd == "teardown":
        # teardown <epic> [--force] [dir]
        force = "--force" in rest
        positional = [a for a in rest if a != "--force"]
        if not positional:
            print("usage: registry.py teardown <epic> [--force] [dir]",
                  file=sys.stderr)
            return 2
        main = _main_from(positional, 1)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        res = teardown(main, positional[0], force=force)
        print(json.dumps(res, indent=2))
        # Exit 3 signals "kept/flagged" so the caller can surface it loudly.
        return 3 if res["kept"] else 0

    if cmd == "worktree-path":
        # worktree-path <epic> [base_root] [dir]
        if not rest:
            print("usage: registry.py worktree-path <epic> [base_root] [dir]",
                  file=sys.stderr)
            return 2
        epic = rest[0]
        base_root = rest[1] if len(rest) > 1 and rest[1] else None
        main = _main_from(rest, 2)
        if not main:
            print("not a git repository", file=sys.stderr)
            return 1
        if not base_root:
            base_root = default_worktree_base(derive_project_id(main))
        print(compute_worktree_path(base_root, epic))
        return 0

    print(f"registry.py: unknown command {cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
