"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import os
import re
import subprocess

from .events import write_notification
from .specs import archive_spec
from .supervisor import (
    CONTROL_FILE,
    HEALTH_FILE,
    pause_file_exists,
)
from .utils import kill_tmux_session, log, run_git

_GIT_STUCK_STATE_MARKERS = [
    ("MERGE_HEAD", "MERGING"),
    ("REVERT_HEAD", "REVERTING"),
    ("CHERRY_PICK_HEAD", "CHERRY-PICKING"),
    ("REBASE_HEAD", "REBASING"),
]


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


class GitRecoveryFailed(Exception):
    """Raised when the orchestrator finds the repo stuck in a merge, revert,
    rebase, or cherry-pick state that it cannot recover from automatically.

    Caught at `main()`, which writes a critical notification and aborts.
    Message includes manual remediation steps.
    """


def is_git_repo(project_dir: str) -> bool:
    """Return True iff `project_dir` is inside a git repository.

    Uses `git rev-parse --git-dir` which succeeds in both standard repos
    and linked worktrees, fails elsewhere. Called at orchestrator startup
    so subsequent git operations have a sane precondition.
    """
    result = run_git(["rev-parse", "--git-dir"], project_dir)
    return result.returncode == 0


def _resolve_git_dir(project_dir: str) -> str | None:
    """Return the absolute path of the actual `.git` directory.

    Supports linked worktrees where `.git` is a file containing
    `gitdir: /abs/path/to/worktrees/foo`. `git rev-parse --git-dir` handles
    both standard repos (returns `.git`) and worktrees (returns the real
    path). Returns `None` if not a git repo or if the command fails.
    """
    result = run_git(["rev-parse", "--git-dir"], project_dir)
    if result.returncode != 0:
        return None
    git_dir = result.stdout.strip()
    if not git_dir:
        return None
    # Standard repo returns ".git"; worktrees return an absolute path.
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(project_dir, git_dir)
    return git_dir


def check_git_clean_recovery(project_dir: str) -> tuple[bool, str]:
    """Check the repo is not stuck in a merge/revert/rebase/cherry-pick state.

    Returns `(is_clean, state_name)` — state_name is the stuck state
    (e.g., "MERGING") or `""` if the repo is clean. Uses `git rev-parse`
    to locate the actual git dir so worktrees (where `.git` is a file,
    not a directory) resolve correctly.

    If the git dir can't be resolved (not a git repo, permissions, etc.),
    returns `(True, "")` on the grounds that this function is called after
    `run_git` operations have already succeeded — the caller is asking
    "did the just-completed abort leave me stuck?", and if git metadata
    suddenly disappeared between calls, the right answer is "I can't tell,
    proceed and let the next git operation surface the real error."
    """
    git_dir = _resolve_git_dir(project_dir)
    if git_dir is None:
        return True, ""
    for marker, name in _GIT_STUCK_STATE_MARKERS:
        if os.path.exists(os.path.join(git_dir, marker)):
            return False, name
    return True, ""


def get_worktree_dirty_summary(project_dir: str) -> str:
    """Return `git status --porcelain` output, or empty string if clean.

    Respects `.gitignore`, so gitignored state files (`.execution-state.json`,
    etc.) don't count as dirty. Caller is expected to have already confirmed
    this is a git repo via `is_git_repo()`; a non-zero exit from `git status`
    after that point indicates a catastrophic condition (corrupt index,
    permissions) which this function surfaces as an empty string — harmless
    on the happy path, but callers should check `is_git_repo()` up front.
    """
    result = run_git(["status", "--porcelain"], project_dir)
    return result.stdout.strip() if result.returncode == 0 else ""


def verify_clean_worktree(project_dir: str) -> tuple[bool, str]:
    """Verify the git worktree is clean before orchestration begins.

    Returns `(is_clean, summary)`. When dirty, `summary` contains the first
    ten lines of `git status --porcelain` for use in user-facing messages.

    Rationale: the orchestrator creates branches, makes commits, and merges.
    Running against a dirty worktree can either (a) entangle the user's
    uncommitted changes into autonomous commits, or (b) silently lose them
    during branch checkouts. Fail fast instead.

    Precondition: caller has already confirmed `project_dir` is a git repo
    via `is_git_repo()`.
    """
    dirty = get_worktree_dirty_summary(project_dir)
    if not dirty:
        return True, ""
    lines = dirty.split("\n")
    summary = "\n  ".join(lines[:10])
    if len(lines) > 10:
        summary += f"\n  ... and {len(lines) - 10} more"
    return False, summary


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
        HEALTH_FILE,
        CONTROL_FILE,
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
                    is_clean, stuck = check_git_clean_recovery(project_dir)
                    if not is_clean:
                        raise GitRecoveryFailed(
                            f"`git merge --abort` did not clean up — repo stuck in {stuck} state. "
                            f"Manual intervention required. Run: cd {project_dir} && git status"
                        )
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


