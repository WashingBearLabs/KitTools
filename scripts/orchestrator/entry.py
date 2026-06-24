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
    new_run_id,
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
    commit_feature_work,
    commit_tracking_files,
    complete_feature,
    is_git_repo,
    is_validation_clean,
    verify_branch_base,
    verify_clean_worktree,
)
from .prompts import persist_learnings
from . import registry
from .sessions import (
    clean_result_files,
    is_session_error,
    kill_active_child_sessions,
    run_claude_session,
    usage_tokens,
)
from .specs import archive_spec, check_dependencies_archived, tag_checkpoint
from .state import (
    StateCorrupt,
    _atomic_json_write,
    accumulate_token_usage,
    get_state_path,
    load_or_create_epic_state,
    load_or_create_state,
    save_state,
)
from .keep_awake import start_keep_awake, stop_keep_awake
from .supervisor import pause_file_exists, wait_for_pause_removal
from .trace_reduce import finalize_run_trace
from .utils import GitCommandError, kill_tmux_session, log, now_iso, run_git


def _update_registry_status(config: dict, status: str) -> None:
    """Best-effort: reflect an execution status transition in the `.kit/` registry.

    The registry lives in the *main* checkout (``config["main_repo"]``), keyed by
    epic (or feature) name. This is a no-op for legacy configs that predate
    worktree isolation — those have no ``main_repo``, run in the user's live
    checkout, and were never registered — so old in-dir executions are wholly
    unaffected. Never raises: a registry write failure must not take down an
    otherwise-healthy execution.
    """
    main_repo = config.get("main_repo")
    if not main_repo:
        return
    try:
        # Prefer the key, but fall back to matching by worktree path so a
        # key/epic-name divergence can't strand the record at "running" (the
        # state file is deleted on cleanup, so the registry is the durable
        # signal that drives the reap).
        registry.reconcile_status(
            main_repo, status,
            key=config.get("epic_name") or config.get("feature_name"),
            worktree=config.get("project_dir"),
        )
    except Exception:
        pass


def register_crash_handler(config: dict) -> None:
    """Register atexit + SIGTERM handlers to detect orchestrator crashes."""
    state_path = get_state_path(config)

    def _on_exit():
        try:
            # Reap any live child `claude` session FIRST so a stopped orchestrator
            # can't leave an orphan that keeps writing partial work and re-dirties
            # the worktree after teardown. No-op on a clean exit (no live child).
            kill_active_child_sessions()
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
            _update_registry_status(config, "crashed")
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

    def _on_signal(signum, frame):
        _on_exit()
        sys.exit(1)

    # Reap the child on any stop signal — not just SIGTERM. SIGINT (Ctrl+C) and
    # SIGHUP (tmux kill-session / terminal close) must also stop the child
    # session, otherwise it's orphaned in its own process group and keeps running.
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _on_signal)


def _elapsed_seconds(start_iso: str | None) -> float | None:
    """Best-effort wall-clock seconds since an ISO-8601 timestamp."""
    if not start_iso:
        return None
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        return round((datetime.now(start.tzinfo) - start).total_seconds(), 1)
    except (ValueError, TypeError):
        return None


def _config_snapshot(config: dict) -> dict:
    """The scaffold 'knobs' this run executed with — recorded on `run.started`
    so an ablation can attribute an outcome change to the knob that changed
    (model set, completion strategy, isolation mode). Without it, two runs that
    differ only by implementer model are indistinguishable in the trace, and the
    experimental design's "hold the model fixed, vary the scaffold" premise is
    unverifiable from the record (T1-C)."""
    try:
        models = get_model_config(config)
    except Exception:
        models = {}
    return {
        "models": models,
        "completion_strategy": config.get("completion_strategy", "none"),
        "worktree_mode": bool(config.get("main_repo")),
        "epic_pause_between_specs": bool(config.get("epic_pause_between_specs")),
    }


def _ensure_run_id(config: dict, state: dict) -> str:
    """Mint a run_id on first launch, or reuse the one persisted in state on
    resume, so every event in a run (across its many sessions) shares an id the
    reducer can upsert on. Stamped on both config (read by log_event) and state
    (durable across sessions)."""
    run_id = state.get("run_id") or config.get("run_id") or new_run_id()
    config["run_id"] = run_id
    state["run_id"] = run_id
    return run_id


def run_single_spec(config: dict) -> None:
    """Execute a single feature spec (original behavior, backwards compatible)."""
    state, is_rerun = load_or_create_state(config)
    # Stamp this process's start so the 24h safety net measures *this* launch,
    # not the epic's original start — resuming a >24h-old run must not re-trip it.
    state["run_started_at"] = now_iso()
    _ensure_run_id(config, state)
    save_state(state, config)
    log_event(
        config, "run.started",
        mode=config["mode"], branch=config["branch_name"],
        max_retries=config.get("max_retries"), is_rerun=is_rerun, epic=False,
        config_snapshot=_config_snapshot(config),
    )

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
    log_event(
        config, "run.completed",
        outcome="completed",
        duration_seconds=_elapsed_seconds(state.get("run_started_at")),
        sessions=state.get("sessions", {}),
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
    validate_session = run_claude_session(validate_prompt, project_dir, model=validator_model)
    validate_output = validate_session.output
    _v_in, _v_out = usage_tokens(validate_session.usage)
    accumulate_token_usage(state, _v_in, _v_out, validate_session.cost_usd)
    _v_est = state.setdefault("token_estimates", {"input": 0, "output": 0})
    _v_est["input"] += len(validate_prompt) // 4
    _v_est["output"] += len(validate_output) // 4
    log_event(
        config, "session.metrics", phase="validate", model=validator_model,
        tokens_input=_v_in, tokens_output=_v_out, cost_usd=validate_session.cost_usd,
        token_estimate_input=len(validate_prompt) // 4,
        token_estimate_output=len(validate_output) // 4,
    )

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

    # Reduce the trace NOW, with live state + before complete_feature cleans up
    # the state file — the Stop hook never fires again after this, so this is the
    # only point the terminal `completed` outcome + token totals get recorded.
    finalize_run_trace(config, state)
    complete_feature(config, state, validation_clean)
    _update_registry_status(config, "completed")


def run_epic(config: dict) -> None:
    """Execute an epic: multiple feature specs in sequence on a shared branch."""
    state, is_rerun = load_or_create_epic_state(config)
    # Stamp this process's start so the 24h safety net measures *this* launch,
    # not the epic's original start — resuming a >24h-old run must not re-trip it.
    state["run_started_at"] = now_iso()
    _ensure_run_id(config, state)
    save_state(state, config)

    project_dir = config["project_dir"]
    epic_name = config["epic_name"]
    epic_specs = config["epic_specs"]
    log_event(
        config, "run.started",
        mode=config["mode"], branch=config["branch_name"],
        max_retries=config.get("max_retries"), is_rerun=is_rerun,
        epic=True, spec_count=len(epic_specs),
        config_snapshot=_config_snapshot(config),
    )

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
            _update_registry_status(config, "blocked")
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
        validate_session = run_claude_session(validate_prompt, project_dir, model=validator_model)
        validate_output = validate_session.output
        state["sessions"]["total"] += 1
        state["sessions"]["validation"] += 1
        _ev_in, _ev_out = usage_tokens(validate_session.usage)
        accumulate_token_usage(state, _ev_in, _ev_out, validate_session.cost_usd)
        _ev_est = state.setdefault("token_estimates", {"input": 0, "output": 0})
        _ev_est["input"] += len(validate_prompt) // 4
        _ev_est["output"] += len(validate_output) // 4
        log_event(
            config, "session.metrics", spec=spec_basename, phase="validate",
            model=validator_model, tokens_input=_ev_in, tokens_output=_ev_out,
            cost_usd=validate_session.cost_usd,
            token_estimate_input=len(validate_prompt) // 4,
            token_estimate_output=len(validate_output) // 4,
        )

        if is_session_error(validate_output):
            log(f"  Validation error: {validate_output[:200]}")
            # Continue anyway — validation is informational

        # Check for pause file (created by validate-implementation if critical findings exist)
        if pause_file_exists(project_dir):
            log(f"  Critical validation findings for {spec_basename}. Pausing.")
            wait_for_pause_removal(project_dir, config=config)
            log("  Resuming after pause.")

        # Commit this spec's work — including any source files the validation
        # session edited directly (in a worktree this stages everything; in a
        # legacy in-dir run it falls back to the narrow tracking-file list).
        commit_feature_work(project_dir, feature_name, config)

        # Tag checkpoint
        tag_checkpoint(project_dir, epic_name, feature_name)

        # Archive feature spec
        archive_spec(project_dir, spec_path, feature_name)

        # Commit archive + tag. warn-only: archive staging is verified inside
        # archive_spec, and commit_feature_work above already committed the
        # spec's pending work.
        run_git(
            ["commit", "-m", f"chore({epic_name}): complete {feature_name}", "--allow-empty"],
            project_dir, warn=True
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
    log_event(
        config, "run.completed",
        outcome="completed",
        duration_seconds=_elapsed_seconds(state.get("run_started_at")),
        sessions=state.get("sessions", {}),
        specs_total=len(epic_specs),
    )

    # Complete the epic using the configured strategy
    validation_clean = is_validation_clean(project_dir)
    # Terminal reduction before cleanup — see run_single_spec for why.
    finalize_run_trace(config, state)
    complete_feature(config, state, validation_clean)
    _update_registry_status(config, "completed")


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

    # Hold a sleep assertion for the run if the user opted in. Released on any
    # exit via atexit (which the signal handlers also trigger through sys.exit).
    _keep_awake_proc = start_keep_awake(config)
    atexit.register(lambda: stop_keep_awake(_keep_awake_proc))

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
    except GitCommandError as e:
        # A git mutation the orchestrator declared fatal (run_git(check=True))
        # failed. Almost always environmental — a dirty tracked file, broken
        # commit config — that retrying can't fix. Abort loudly rather than
        # record success the work never earned.
        log(f"FATAL: {e}")
        write_notification(
            config, "execution_blocked",
            "Git command failed — execution aborted",
            str(e),
            severity="critical",
        )
        log_event(config, "abort_git_command_failed", severity="critical", message=str(e))
        sys.exit(1)
    finally:
        # Catch-all terminal reduction for failure/abort/exit paths (the normal
        # completion path already finalized with live state before cleanup).
        # Reads the state file if still present; no-op once cleaned up.
        finalize_run_trace(config)

    log("Orchestrator finished.")


