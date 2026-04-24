"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import argparse
import atexit
import json
import os
import signal
import sys

from .config import get_model_config, load_config
from .events import (
    NOTIFICATION_FILE,
    log_event,
    write_notification,
)
from .execution_log import (
    get_log_path,
    init_execution_log,
    log_completion,
)
from .executor import execute_spec_stories
from .git_ops import (
    GitRecoveryFailed,
    cleanup_attempt_branches,
    commit_tracking_files,
    complete_feature,
    is_git_repo,
    is_validation_clean,
    verify_branch_base,
    verify_clean_worktree,
)
from .prompts import persist_learnings
from .sessions import clean_result_files, is_session_error, run_claude_session
from .specs import archive_spec, check_dependencies_archived, tag_checkpoint
from .state import (
    StateCorrupt,
    _atomic_json_write,
    get_state_path,
    load_or_create_epic_state,
    load_or_create_state,
    save_state,
)
from .supervisor import pause_file_exists, wait_for_pause_removal
from .utils import kill_tmux_session, log, now_iso, run_git


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
            _atomic_json_write(state_path, state)
            feature = config.get("feature_name") or config.get("epic_name", "unknown")
            write_notification(
                config, "execution_crashed",
                "Execution crashed",
                f"Orchestrator exited unexpectedly for {feature}",
                severity="critical",
            )
            log_event(
                config, "orchestrator_crashed", severity="critical",
                feature=feature,
            )
        except Exception:
            pass

    atexit.register(_on_exit)

    def _on_sigterm(signum, frame):
        _on_exit()
        sys.exit(1)

    signal.signal(signal.SIGTERM, _on_sigterm)


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
    commit_tracking_files(project_dir, config.get("feature_name", "feature"))

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
    persist_learnings(project_dir, state)
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
    validator_model = get_model_config(config)["validator"]
    log(f"Running implementation validation (model={validator_model})...")
    validate_prompt = (
        f"Run /kit-tools:validate-implementation for feature spec {spec_basename}. "
        f"Mode: autonomous. Branch: {branch}."
    )
    validate_output = run_claude_session(validate_prompt, project_dir, model=validator_model)

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
    commit_tracking_files(project_dir, epic_name)

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
        validator_model = get_model_config(config)["validator"]
        log(f"  All stories complete for {spec_basename}. Validating (model={validator_model})...")
        validate_prompt = (
            f"Run /kit-tools:validate-implementation for feature spec {spec_basename}. "
            f"Mode: autonomous. Branch: {config['branch_name']}. "
            f"This is part of an epic — do NOT invoke complete-implementation."
        )
        validate_output = run_claude_session(validate_prompt, project_dir, model=validator_model)
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
    persist_learnings(project_dir, state)
    write_notification(
        config, "execution_complete",
        "Epic complete",
        f"All {len(epic_specs)} feature specs complete for epic {epic_name}",
        severity="info",
    )

    # Complete the epic using the configured strategy
    validation_clean = is_validation_clean(project_dir)
    complete_feature(config, state, validation_clean)


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

    # Verify we're in a git repo at all before the worktree check below —
    # otherwise `git status --porcelain` returns empty stdout on failure,
    # which verify_clean_worktree would misread as "clean" and the
    # orchestrator would proceed, then fail confusingly on branch creation.
    if not is_git_repo(config["project_dir"]):
        log(f"FATAL: {config['project_dir']} is not a git repository.")
        log("The orchestrator creates feature branches and commits — it requires a git repo.")
        write_notification(
            config, "execution_blocked",
            "Orchestrator aborted — not a git repository",
            f"{config['project_dir']} is not a git repository. Initialise one or run the orchestrator from inside an existing repo.",
            severity="critical",
        )
        log_event(config, "abort_not_git_repo", severity="critical")
        sys.exit(1)

    # Verify clean worktree before touching anything — the orchestrator
    # creates branches, commits, and merges, so dirty state either entangles
    # user work into autonomous commits or gets silently lost on checkout.
    is_clean, dirty_summary = verify_clean_worktree(config["project_dir"])
    if not is_clean:
        log("FATAL: Worktree has uncommitted changes. Orchestrator will not proceed.")
        log("Commit, stash, or revert changes before running. Dirty entries:")
        log(f"  {dirty_summary}")
        write_notification(
            config, "execution_blocked",
            "Orchestrator aborted — dirty worktree",
            "Uncommitted changes detected. Commit, stash, or revert before running.",
            severity="critical",
        )
        log_event(
            config, "abort_dirty_worktree", severity="critical",
            dirty_line_count=len(dirty_summary.split("\n")),
        )
        sys.exit(1)

    register_crash_handler(config)

    try:
        if config.get("epic_specs"):
            run_epic(config)
        else:
            run_single_spec(config)
    except StateCorrupt as e:
        log(f"FATAL: {e}")
        write_notification(
            config, "execution_blocked",
            "State file corrupt or incompatible",
            str(e),
            severity="critical",
        )
        log_event(config, "abort_state_corrupt", severity="critical", message=str(e))
        sys.exit(1)
    except GitRecoveryFailed as e:
        log(f"FATAL: {e}")
        write_notification(
            config, "execution_blocked",
            "Git recovery failed — manual intervention required",
            str(e),
            severity="critical",
        )
        log_event(config, "abort_git_recovery_failed", severity="critical", message=str(e))
        sys.exit(1)

    log("Orchestrator finished.")


