"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import os
import sys

from .config import get_model_config
from .events import write_notification
from .execution_log import log_story_failure, log_story_success
from .git_ops import (
    check_git_clean_recovery,
    commit_tracking_files,
    create_attempt_branch,
    delete_attempt_branch,
    get_head_commit,
    GitRecoveryFailed,
    merge_attempt_branch,
)
from .prompts import (
    DIFF_CONTENT_MAX,
    build_implementation_prompt,
    build_verification_prompt,
    check_and_trim_prompt,
    classify_failure,
)
from .sessions import (
    IMPL_SESSION_TIMEOUT,
    VERIFY_SESSION_TIMEOUT,
    clean_result_files,
    extract_learnings_from_results,
    get_size_timeouts,
    is_session_error,
    read_implementation_result,
    read_verification_result,
    run_claude_session,
)
from .specs import (
    find_next_uncompleted_story,
    parse_spec_frontmatter,
    update_spec_checkboxes,
)
from .state import (
    _store_attempt_diff,
    save_state,
    update_state_story,
)
from .supervisor import (
    check_orchestrator_duration,
    handle_control_action,
    pause_file_exists,
    read_control_file,
    wait_for_pause_removal,
    write_health_snapshot,
)
from .tests_metrics import (
    check_test_mapping_gaps,
    detect_test_command,
    make_fail_fast,
    pre_flight_check,
    run_regression_check,
    update_test_metrics,
)
from .utils import log, run_git

def execute_spec_stories(
    spec_path: str, feature_name: str, config: dict, state: dict,
    spec_key: str | None = None
) -> dict:
    """Execute all stories in a single feature spec. Returns updated state.

    Args:
        spec_path: Absolute path to the feature spec file.
        feature_name: Feature name for commit messages.
        config: Orchestrator config dict.
        state: Execution state dict.
        spec_key: If set, story state lives under state["specs"][spec_key] (epic mode).
                 If None, story state lives under state["stories"] (single mode).
    """
    project_dir = config["project_dir"]
    mode = config["mode"]
    max_retries = config.get("max_retries")

    # Auto-detect test command once per feature spec execution
    test_command = detect_test_command(project_dir)
    fail_fast_test = make_fail_fast(test_command) if test_command else None
    if test_command:
        log(f"  Detected test command: {test_command}")

    # Compute size-based timeouts from spec frontmatter
    impl_timeout, verify_timeout = get_size_timeouts(spec_path)
    if impl_timeout != IMPL_SESSION_TIMEOUT or verify_timeout != VERIFY_SESSION_TIMEOUT:
        size_fm = parse_spec_frontmatter(spec_path) if spec_path and os.path.exists(spec_path) else {}
        log(f"  Story size: {size_fm.get('size', 'M')}, impl timeout: {impl_timeout}s, verify timeout: {verify_timeout}s")

    # Determine which stories_state dict to use for find_next_uncompleted_story
    if spec_key is not None:
        stories_state = state["specs"][spec_key]
    else:
        stories_state = state

    # Track files already warned about for mapping gaps (dedup across stories)
    _warned_mapping_files: set[str] = set()

    while True:
        # Check pause file between stories
        if pause_file_exists(project_dir):
            wait_for_pause_removal(project_dir, config=config)

        # --- Supervisor control file check (between stories) ---
        control = read_control_file(config)
        if control:
            result = handle_control_action(
                control, config, state, spec_path, feature_name, spec_key
            )
            if result == "abort":
                commit_tracking_files(project_dir, feature_name)
                sys.exit(1)
            elif result == "pause":
                wait_for_pause_removal(project_dir, config=config)
            elif result == "stories_updated":
                # Re-derive stories_state after split/skip
                if spec_key is not None:
                    stories_state = state["specs"][spec_key]
                else:
                    stories_state = state
                continue  # Re-enter loop to find next story

        # --- 24h safety net ---
        if check_orchestrator_duration(state):
            state["status"] = "failed"
            save_state(state, config)
            write_notification(
                config, "duration_limit",
                "Orchestrator exceeded 24h limit",
                "Safety net triggered — orchestrator has been running for over 24 hours.",
                severity="critical",
            )
            commit_tracking_files(project_dir, feature_name)
            sys.exit(1)

        # Find next uncompleted story
        story = find_next_uncompleted_story(spec_path, stories_state)
        if not story:
            return state  # All stories done

        story_state_entry = stories_state.get("stories", {}).get(story["id"], {})
        attempt = story_state_entry.get("attempts", 0)
        feature_branch = config["branch_name"]

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
                        commit_tracking_files(project_dir, feature_name)
                        clean_result_files(project_dir)
                        sys.exit(0)
                    attempt = 1  # Reset for new round
                    continue
                else:
                    log(f"Story {story['id']} exceeded max retries ({max_retries}). Stopping.")
                    state["status"] = "failed"
                    update_state_story(
                        state, story["id"], "failed", attempt - 1,
                        failure=f"Exceeded max retries ({max_retries})",
                        spec_key=spec_key
                    )
                    save_state(state, config)
                    write_notification(
                        config, "story_failed",
                        f"Story {story['id']} failed",
                        f"{story['id']}: {story['title']} exceeded {max_retries} retries",
                        severity="critical",
                    )
                    commit_tracking_files(project_dir, feature_name)
                    clean_result_files(project_dir)
                    sys.exit(1)

            # Clean result files before each attempt
            clean_result_files(project_dir)

            # --- Pre-flight checks (first attempt only) ---
            if attempt == 1:
                pre_flight_check(story, config, state, spec_key)
                save_state(state, config)

            # --- Capture pre-attempt HEAD for unambiguous diffs ---
            pre_attempt_head = get_head_commit(project_dir)

            # --- Create attempt branch ---
            attempt_branch = create_attempt_branch(
                project_dir, feature_branch, story["id"], attempt
            )

            # --- Implementation session ---
            log(f"Implementing {story['id']}: {story['title']} (attempt {attempt})...")
            update_state_story(state, story["id"], "in_progress", attempt, spec_key=spec_key)
            save_state(state, config)
            write_health_snapshot(config, state, story["id"], attempt, event="attempt_start")

            prompt = build_implementation_prompt(
                story, config, state, attempt,
                feature_name=feature_name, spec_path=spec_path, spec_key=spec_key
            )
            prompt = check_and_trim_prompt(prompt, "implementation")

            # Estimate input tokens
            prompt_chars = len(prompt)
            models = get_model_config(config)
            impl_model = models["implementer"]
            log(f"  Session timeout: {impl_timeout}s (implementation, model={impl_model})")
            impl_output = run_claude_session(
                prompt, project_dir, timeout=impl_timeout, model=impl_model
            )
            output_chars = len(impl_output)

            state["sessions"]["total"] += 1
            state["sessions"]["implementation"] += 1
            # Track token estimates
            token_est = state.setdefault("token_estimates", {"input": 0, "output": 0})
            token_est["input"] += prompt_chars // 4
            token_est["output"] += output_chars // 4
            log(f"  Session tokens: ~{prompt_chars // 4000}k input, ~{output_chars // 4000}k output")
            save_state(state, config)

            # Check for session errors
            if impl_output.startswith("SESSION_ERROR_PERMANENT:"):
                f_type = classify_failure(impl_output, None, None)
                log(f"  Permanent session error [{f_type}]: {impl_output[:200]}")
                learnings = [f"Permanent error: {impl_output[:200]}"]
                log_story_failure(story, attempt, config, impl_output[:500], learnings)
                update_state_story(
                    state, story["id"], "failed", attempt, learnings, impl_output[:500],
                    spec_key=spec_key, failure_type=f_type
                )
                state["status"] = "failed"
                save_state(state, config)
                write_notification(
                    config, "story_failed",
                    f"Story {story['id']} permanent error",
                    f"{story['id']}: {impl_output[:200]}",
                    severity="critical",
                )
                delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                clean_result_files(project_dir)
                sys.exit(1)

            if impl_output.startswith("SESSION_ERROR:"):
                f_type = classify_failure(impl_output, None, None)
                log(f"  Implementation session error [{f_type}]: {impl_output[:200]}")
                learnings = [f"Session error: {impl_output[:200]}"]
                log_story_failure(story, attempt, config, impl_output[:500], learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt, learnings, impl_output[:500],
                    spec_key=spec_key, failure_type=f_type
                )
                save_state(state, config)
                # Delete the failed attempt branch (no diff to capture on session error)
                delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                clean_result_files(project_dir)
                continue

            # --- Read implementation result from file ---
            impl_result, impl_error = read_implementation_result(project_dir)
            if impl_error:
                log(f"  Implementation result: {impl_error}")

            # --- Get files changed from git (for verifier) ---
            git_files_result = run_git(
                ["diff", "--name-only", f"{pre_attempt_head}..HEAD"], project_dir
            )
            files_changed_from_git = git_files_result.stdout.strip() if git_files_result.returncode == 0 else ""

            # --- Check test mapping gaps (informational, deduped across stories) ---
            check_test_mapping_gaps(files_changed_from_git, project_dir, _warned_mapping_files)

            # --- Get diff stat (for verifier) ---
            diff_stat_result = run_git(
                ["diff", "--stat", f"{pre_attempt_head}..HEAD"], project_dir
            )
            diff_stat = diff_stat_result.stdout.strip() if diff_stat_result.returncode == 0 else ""

            # --- Capture inline diff content (for verifier) ---
            diff_content_result = run_git(
                ["diff", f"{pre_attempt_head}..HEAD"], project_dir
            )
            raw_diff = diff_content_result.stdout.strip() if diff_content_result.returncode == 0 else ""
            if len(raw_diff) <= DIFF_CONTENT_MAX:
                diff_content = raw_diff
            else:
                diff_content = (
                    f"[Diff truncated — {len(raw_diff)} chars exceeds {DIFF_CONTENT_MAX} limit. "
                    f"Use the Read tool to examine full files.]\n\n"
                    f"Diff stat:\n{diff_stat}"
                )

            # --- Verification session ---
            log(f"  Verifying {story['id']}...")
            verify_prompt = build_verification_prompt(
                story, config, files_changed_from_git,
                diff_stat=diff_stat, test_command=fail_fast_test, spec_path=spec_path,
                diff_content=diff_content
            )
            verify_prompt = check_and_trim_prompt(verify_prompt, "verification")

            verify_prompt_chars = len(verify_prompt)
            verify_model = get_model_config(config)["verifier"]
            log(f"  Session timeout: {verify_timeout}s (verification, model={verify_model})")
            verify_output = run_claude_session(
                verify_prompt, project_dir, timeout=verify_timeout, model=verify_model
            )
            verify_output_chars = len(verify_output)

            state["sessions"]["total"] += 1
            state["sessions"]["verification"] += 1
            token_est["input"] += verify_prompt_chars // 4
            token_est["output"] += verify_output_chars // 4
            log(f"  Session tokens: ~{verify_prompt_chars // 4000}k input, ~{verify_output_chars // 4000}k output")
            save_state(state, config)

            # --- Check for verification session errors ---
            if is_session_error(verify_output):
                f_type = classify_failure("", verify_output, None)
                log(f"  Verification session error [{f_type}]: {verify_output[:200]}")
                learnings = extract_learnings_from_results(impl_result, None)
                learnings.append(f"Verify session error: {verify_output[:200]}")
                log_story_failure(story, attempt, config, verify_output[:500], learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, verify_output[:500], spec_key=spec_key,
                    failure_type=f_type
                )
                save_state(state, config)
                attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                save_state(state, config)
                clean_result_files(project_dir)
                continue

            # --- Read verification result from file ---
            verdict, verify_error = read_verification_result(project_dir)

            # Record test metrics regardless of verdict outcome
            if verdict:
                update_test_metrics(project_dir, verdict, story["id"])

            if verify_error:
                # Result file missing or invalid — treat as retryable failure
                log(f"  Verification result error: {verify_error}")
                learnings = extract_learnings_from_results(impl_result, None)
                log_story_failure(story, attempt, config, verify_error, learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, verify_error, spec_key=spec_key
                )
                save_state(state, config)
                # Capture diff as retry context, then delete attempt branch
                attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                save_state(state, config)
                clean_result_files(project_dir)
                continue

            if verdict["verdict"] in ("pass", "pass_with_warnings"):
                learnings = extract_learnings_from_results(impl_result, verdict)
                verdict_warnings = verdict.get("warnings", []) if verdict["verdict"] == "pass_with_warnings" else []
                if verdict_warnings:
                    log(f"  {story['id']} PASSED with {len(verdict_warnings)} warnings (attempt {attempt})")
                else:
                    log(f"  {story['id']} PASSED (attempt {attempt})")
                # Merge attempt branch into feature branch
                merge_ok = merge_attempt_branch(project_dir, feature_branch, attempt_branch)
                if not merge_ok:
                    log(f"  Merge conflict — aborting merge, will retry implementation.")
                    run_git(["merge", "--abort"], project_dir, check=True)
                    is_clean, stuck = check_git_clean_recovery(project_dir)
                    if not is_clean:
                        raise GitRecoveryFailed(
                            f"`git merge --abort` did not clean up after merge conflict — repo stuck in {stuck} state. "
                            f"Cannot safely retry. Manual intervention required: cd {project_dir} && git status"
                        )
                    learnings.append("Merge conflict on attempt branch — retry with fresh approach")
                    log_story_failure(story, attempt, config, "Merge conflict", learnings)
                    update_state_story(
                        state, story["id"], "retrying", attempt,
                        learnings, "Merge conflict", spec_key=spec_key
                    )
                    save_state(state, config)
                    attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                    _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                    save_state(state, config)
                    clean_result_files(project_dir)
                    continue
                # Run cross-story regression check
                reg_passed, reg_msg = run_regression_check(
                    project_dir, state, story["id"], fail_fast_test, spec_key
                )
                if not reg_passed:
                    log(f"  REGRESSION detected after merging {story['id']}!")
                    log(f"  {reg_msg[:300]}")
                    # Revert the merge to keep feature branch clean
                    merge_head = get_head_commit(project_dir)
                    revert_result = run_git(["revert", "--no-edit", merge_head], project_dir, check=True)
                    if revert_result.returncode != 0:
                        # Revert itself failed — most likely a conflict during revert.
                        # Check whether the repo is stuck or whether revert failed
                        # for a non-conflict reason. Either way, don't proceed.
                        is_clean, stuck = check_git_clean_recovery(project_dir)
                        if not is_clean:
                            raise GitRecoveryFailed(
                                f"`git revert` conflicted on {merge_head[:8]} — repo stuck in {stuck} state. "
                                f"Manual intervention required: cd {project_dir} && git status, "
                                f"resolve conflicts, then `git revert --continue` or `git revert --abort`."
                            )
                        raise GitRecoveryFailed(
                            f"`git revert {merge_head[:8]}` failed (exit {revert_result.returncode}) "
                            f"but repo is not stuck: {revert_result.stderr.strip()[:200]}. "
                            f"Manual review required."
                        )
                    log(f"  Reverted merge commit {merge_head[:8]}")
                    update_state_story(
                        state, story["id"], "failed", attempt,
                        [f"Regression: {reg_msg[:200]}"],
                        f"Regression detected: {reg_msg[:500]}",
                        spec_key=spec_key, failure_type="REGRESSION"
                    )
                    state["status"] = "failed"
                    save_state(state, config)
                    write_notification(
                        config, "regression_detected",
                        f"Regression detected after {story['id']}",
                        f"{story['id']}: {reg_msg[:200]}",
                        severity="critical",
                    )
                    commit_tracking_files(project_dir, feature_name)
                    clean_result_files(project_dir)
                    sys.exit(1)
                elif "Skipped" not in reg_msg:
                    log(f"  Regression check: {reg_msg}")

                # Update feature spec checkboxes on the feature branch
                if update_spec_checkboxes(spec_path, story["id"]):
                    log(f"  Updated feature spec checkboxes for {story['id']}")
                    run_git(["add", spec_path], project_dir, check=True)
                    run_git(
                        ["commit", "-m", f"chore({feature_name}): mark {story['id']} criteria complete"],
                        project_dir, check=True
                    )
                # Store files_changed for regression detection
                changed_file_list = [f.strip() for f in files_changed_from_git.split("\n") if f.strip()]
                log_story_success(story, attempt, config, learnings, feature_name=feature_name)
                update_state_story(
                    state, story["id"], "completed", attempt, learnings,
                    spec_key=spec_key, warnings=verdict_warnings,
                    files_changed=changed_file_list
                )
                save_state(state, config)
                write_notification(
                    config, "story_complete",
                    f"Story {story['id']} passed",
                    f"{story['id']}: {story['title']} (attempt {attempt})",
                    severity="info",
                )
                clean_result_files(project_dir)
                write_health_snapshot(config, state, story["id"], attempt, event="story_passed")
                break  # Move to next story
            else:
                failure_details = verdict.get("recommendations", "Verification failed")
                learnings = extract_learnings_from_results(impl_result, verdict)
                f_type = classify_failure("", verify_output, verdict)
                log(f"  {story['id']} FAILED verification (attempt {attempt}) [{f_type}]")
                log(f"  Reason: {str(failure_details)[:200]}")
                log_story_failure(story, attempt, config, str(failure_details), learnings)
                update_state_story(
                    state, story["id"], "retrying", attempt,
                    learnings, str(failure_details), spec_key=spec_key,
                    failure_type=f_type
                )
                save_state(state, config)
                # Capture diff as retry context, then delete attempt branch
                attempt_diff = delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                save_state(state, config)
                clean_result_files(project_dir)
                write_health_snapshot(config, state, story["id"], attempt, event="attempt_failed")
                # Loop continues to next attempt

    return state


