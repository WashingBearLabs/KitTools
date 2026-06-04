"""Worktree lifecycle helpers for KitTools execution isolation.

Part of the KitTools orchestrator package. Provides the mechanics for running
an epic execution in its own git worktree instead of the user's live checkout:
create/remove/list worktrees, run the per-project environment bootstrap, and
link (or copy) the gitignored secret files a fresh worktree lacks.

Worktrees share the object store and refs but **not** gitignored working files,
so a fresh worktree has no ``.venv``/``node_modules``/``.env``. Two things close
that gap:
- **env_bootstrap** — ordered shell commands (e.g. ``uv sync``, ``pnpm install``)
  that make the worktree runnable. These come from the project's *committed*
  ``kit_tools/worktree.yaml`` contract and are therefore trusted input; the
  ``execute-epic`` skill echoes them and confirms before running.
- **env_link** — gitignored config/secret files (``.env`` etc.) symlinked from
  the main checkout into the worktree. Symlinks are preferred over copies so a
  secret never gets *duplicated* outside the repo; ``link_env_files`` only falls
  back to copying where symlinks are unavailable (e.g. unprivileged Windows),
  and records which files were copied so teardown can scrub them.
"""
from __future__ import annotations

import os
import shutil

import yaml

from .utils import log, run_git

CONTRACT_RELPATH = os.path.join("kit_tools", "worktree.yaml")

# Sane defaults when no contract is present — the feature degrades to "no
# bootstrap, default worktree root, remove the tree on a clean finish".
_DEFAULT_CONTRACT = {
    "root": None,
    "env_bootstrap": [],
    "env_link": [],
    "cleanup_policy": "remove-on-success",
}

_VALID_CLEANUP = frozenset(
    {"remove-on-success", "remove-always", "keep-always"}
)


def load_contract(main_repo: str) -> dict:
    """Read the committed ``kit_tools/worktree.yaml`` contract.

    Returns a dict with the keys ``root``, ``env_bootstrap``, ``env_link`` and
    ``cleanup_policy``, falling back to safe defaults for any missing or
    malformed field. Never raises: a broken contract degrades to defaults with
    a logged warning rather than aborting an execution.
    """
    contract = dict(_DEFAULT_CONTRACT)
    path = os.path.join(main_repo, CONTRACT_RELPATH)
    if not os.path.exists(path):
        return contract
    try:
        with open(path, "r") as f:
            loaded = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        log(f"  WARNING: could not read {CONTRACT_RELPATH}: {e}. Using defaults.")
        return contract
    if not isinstance(loaded, dict):
        log(f"  WARNING: {CONTRACT_RELPATH} is not a mapping. Using defaults.")
        return contract

    root = loaded.get("root")
    if isinstance(root, str) and root.strip():
        contract["root"] = root.strip()

    for list_key in ("env_bootstrap", "env_link"):
        value = loaded.get(list_key)
        if isinstance(value, list):
            contract[list_key] = [str(v) for v in value if str(v).strip()]

    policy = loaded.get("cleanup_policy")
    if isinstance(policy, str) and policy.strip() in _VALID_CLEANUP:
        contract["cleanup_policy"] = policy.strip()

    return contract


# --- Worktree CRUD --------------------------------------------------------


def branch_exists(main_repo: str, branch: str) -> bool:
    """Return True if ``branch`` already exists locally."""
    result = run_git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
                     main_repo)
    return result.returncode == 0


def add_worktree(main_repo: str, worktree_path: str, branch: str,
                 base: str = "main"):
    """Create a worktree at ``worktree_path`` checked out on ``branch``.

    If ``branch`` does not exist yet it is created from ``base`` (the new-epic
    path). If it already exists the worktree simply attaches to it (the resume
    path). The parent directory is created first so a configured root like
    ``~/.kit/worktrees/<project>`` need not pre-exist.

    Returns the ``CompletedProcess`` of the ``git worktree add`` call.
    """
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)
    if branch_exists(main_repo, branch):
        args = ["worktree", "add", worktree_path, branch]
    else:
        args = ["worktree", "add", worktree_path, "-b", branch, base]
    result = run_git(args, main_repo, check=True)
    if result.returncode == 0:
        log(f"  Created worktree {worktree_path} on branch {branch}")
    return result


def remove_worktree(main_repo: str, worktree_path: str, force: bool = False):
    """Remove a worktree. ``force=True`` discards uncommitted changes.

    Teardown should call this *without* ``force`` so git refuses to remove a
    dirty worktree — the caller then flags it rather than silently destroying
    work. Returns the ``CompletedProcess``.
    """
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(worktree_path)
    return run_git(args, main_repo, check=True)


def prune_worktrees(main_repo: str):
    """Prune registry entries for worktrees whose directories were deleted."""
    return run_git(["worktree", "prune"], main_repo)


def list_worktrees(main_repo: str) -> list[dict]:
    """Parse ``git worktree list --porcelain`` into a list of dicts.

    Each dict carries the keys git emits for that entry — always ``path``, plus
    some of ``head``, ``branch`` (short name), ``bare``, ``detached``,
    ``locked``, ``prunable``.
    """
    result = run_git(["worktree", "list", "--porcelain"], main_repo)
    if result.returncode != 0:
        return []
    entries: list[dict] = []
    current: dict = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            if current:
                entries.append(current)
            current = {"path": line[len("worktree "):]}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            current["branch"] = ref.replace("refs/heads/", "", 1)
        elif line in ("bare", "detached"):
            current[line] = True
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    if current:
        entries.append(current)
    return entries


# --- Environment bootstrap & secret linking -------------------------------


def run_env_bootstrap(worktree_path: str, commands: list[str]) -> list[dict]:
    """Run each bootstrap command (in order) with cwd set to the worktree.

    Returns one result dict per command: ``{"command", "returncode", "stderr"}``.
    Execution stops at the first failure so a broken dependency install doesn't
    cascade into confusing downstream errors. SECURITY: ``commands`` originate
    from the committed contract and are assumed to have been echoed/confirmed by
    the caller — this function does not prompt.
    """
    import subprocess

    results: list[dict] = []
    for command in commands:
        log(f"  env_bootstrap: {command}")
        proc = subprocess.run(
            command, shell=True, cwd=worktree_path,
            capture_output=True, text=True,
        )
        results.append({
            "command": command,
            "returncode": proc.returncode,
            "stderr": proc.stderr.strip()[:500],
        })
        if proc.returncode != 0:
            log(f"  env_bootstrap FAILED ({proc.returncode}): {command}")
            break
    return results


def link_env_files(main_repo: str, worktree_path: str,
                   files: list[str]) -> list[dict]:
    """Make gitignored secret/config files available inside the worktree.

    Each entry in ``files`` is a path relative to the repo root. The source is
    resolved against ``main_repo``; the destination is the same relative path
    inside ``worktree_path``. Prefers a symlink (no secret duplication); falls
    back to a copy only when symlinking is unavailable.

    Returns one record per attempted file:
    ``{"file", "method", "ok"}`` where ``method`` is ``"symlink"``, ``"copy"``
    or ``"skip"`` (source missing). Records with ``method == "copy"`` are what
    teardown must scrub.
    """
    records: list[dict] = []
    for rel in files:
        src = os.path.join(main_repo, rel)
        dst = os.path.join(worktree_path, rel)
        if not os.path.exists(src):
            log(f"  env_link: source {rel} not found in main checkout — skipping")
            records.append({"file": rel, "method": "skip", "ok": False})
            continue
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        # Replace any pre-existing dst (a fresh worktree shouldn't have it, but
        # be idempotent for resume).
        try:
            if os.path.islink(dst) or os.path.exists(dst):
                os.remove(dst)
        except OSError:
            pass
        try:
            os.symlink(os.path.abspath(src), dst)
            records.append({"file": rel, "method": "symlink", "ok": True})
        except (OSError, NotImplementedError):
            # Windows without symlink privilege, or a filesystem that refuses
            # symlinks — fall back to copying and mark it for scrubbing.
            try:
                shutil.copy2(src, dst)
                log(f"  env_link: symlink unavailable, copied {rel} "
                    f"(will scrub on teardown)")
                records.append({"file": rel, "method": "copy", "ok": True})
            except OSError as e:
                log(f"  env_link: failed to provision {rel}: {e}")
                records.append({"file": rel, "method": "skip", "ok": False})
    return records


def scrub_env_files(worktree_path: str, link_records: list[dict]) -> None:
    """Remove provisioned secret files from a worktree.

    Removes both symlinks (harmless, but tidy) and — critically — any files
    that were *copied* in, so an abandoned/kept worktree never leaves a real
    secret sitting outside the repo's gitignore protection. Best-effort.
    """
    for record in link_records:
        if record.get("method") not in ("symlink", "copy"):
            continue
        target = os.path.join(worktree_path, record["file"])
        try:
            if os.path.islink(target) or os.path.exists(target):
                os.remove(target)
        except OSError as e:
            log(f"  scrub: could not remove {record['file']}: {e}")
