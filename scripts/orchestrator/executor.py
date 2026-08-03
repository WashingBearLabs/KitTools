"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import os
import sys

from .config import get_model_config
from .events import log_event, write_notification
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
    usage_tokens,
)
from .specs import (
    execution_order_note,
    find_next_uncompleted_story,
    parse_spec_frontmatter,
    update_spec_checkboxes,
)
from .state import (
    _store_attempt_diff,
    accumulate_token_usage,
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

    # Compute size-based timeouts and model escalation from spec frontmatter
    impl_timeout, verify_timeout = get_size_timeouts(spec_path)
    spec_size = "M"
    if spec_path and os.path.exists(spec_path):
        spec_size = str(parse_spec_frontmatter(spec_path).get("size", "M")).upper()
    if impl_timeout != IMPL_SESSION_TIMEOUT or verify_timeout != VERIFY_SESSION_TIMEOUT:
        log(f"  Story size: {spec_size}, impl timeout: {impl_timeout}s, verify timeout: {verify_timeout}s")

    # Surface a declared story execution order once per spec — the author needs
    # to SEE it was read (a supervisor split can change it mid-run; the walk
    # re-derives order from the spec file each iteration either way).
    order_note = execution_order_note(spec_path)
    if order_note:
        log(f"  {order_note}")

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

            if attempt >= 2:
                log_event(
                    config, "retry.triggered", spec=spec_key, story=story["id"],
                    attempt=attempt, max_attempts=max_retries,
                )

            # Check retry limit
            if max_retries is not None and attempt > max_retries:
                if mode == "guarded":
                    log(f"Story {story['id']} failed after {max_retries} attempts.")
                    # Pause via the standard, monitorable mechanism — NOT a
                    # blocking stdin read. A detached/tmux orchestrator has no
                    # interactive stdin, and a raw input() is invisible to
                    # /kit-tools:execution-status and the supervisor (they see
                    # status:running + a frozen heartbeat, indistinguishable
                    # from a hang — a run once sat silently parked overnight).
                    # Writing the pause file + paused status + a notification
                    # makes it visible, and a human OR the supervisor can resume
                    # it (remove .pause_execution) or intervene with a control
                    # action (skip/split), honored below.
                    log("Guarded mode: pausing for review (retries exhausted).")
                    pause_path = os.path.join(project_dir, "kit_tools", ".pause_execution")
                    try:
                        with open(pause_path, "w") as f:
                            f.write(
                                f"Guarded mode: story {story['id']} exhausted "
                                f"{max_retries} retries.\nRemove this file to retry "
                                f"the story, or send a skip/split via "
                                f"/kit-tools:execution-status.\n"
                            )
                    except OSError:
                        pass
                    state["status"] = "paused"
                    save_state(state, config)
                    commit_tracking_files(project_dir, feature_name)
                    write_notification(
                        config, "execution_paused",
                        f"Guarded pause: {story['id']} retries exhausted",
                        f"Story {story['id']} failed {max_retries} attempts. "
                        f"Remove .pause_execution to retry, or send a skip/split "
                        f"control action.",
                        severity="warning",
                    )
                    wait_for_pause_removal(project_dir, config=config)
                    # On resume, honor any supervisor control action written
                    # while paused (skip/split/pause/abort).
                    control = read_control_file(config)
                    if control:
                        result = handle_control_action(
                            control, config, state, spec_path, feature_name, spec_key
                        )
                        if result == "abort":
                            commit_tracking_files(project_dir, feature_name)
                            clean_result_files(project_dir)
                            sys.exit(1)
                        if result == "stories_updated":
                            # Story was skipped/split — leave the attempt loop so
                            # the per-story loop re-derives and picks the next.
                            if spec_key is not None:
                                stories_state = state["specs"][spec_key]
                            else:
                                stories_state = state
                            break
                    state["status"] = "running"
                    save_state(state, config)
                    attempt = 1  # Reset for a new round of retries
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
            base_impl_model = models["implementer"]
            impl_model = base_impl_model
            # get_model_config() guarantees a fully-normalized {to, on_attempt,
            # sizes} dict here (never a bare string, never missing keys) — index
            # directly rather than re-defaulting, so this trusts one source of
            # truth for the policy instead of silently disagreeing with it.
            esc_policy = models["escalation"]
            if attempt >= esc_policy["on_attempt"] and spec_size in esc_policy["sizes"]:
                impl_model = esc_policy["to"]
                if impl_model != base_impl_model:
                    log(f"  Escalating to {impl_model} for retry of size-{spec_size} story")
                    log_event(
                        config, "model.escalated", spec=spec_key, story=story["id"],
                        from_model=base_impl_model, to_model=impl_model,
                        reason="retry-large-spec", spec_size=spec_size, attempt=attempt,
                    )
            log(f"  Session timeout: {impl_timeout}s (implementation, model={impl_model})")
            log_event(
                config, "story.implement.started", spec=spec_key, story=story["id"],
                actor={"kind": "agent", "id": "story-implementer", "model": impl_model},
                attempt=attempt, spec_size=spec_size,
            )
            impl_session = run_claude_session(
                prompt, project_dir, timeout=impl_timeout, model=impl_model
            )
            impl_output = impl_session.output
            output_chars = len(impl_output)

            state["sessions"]["total"] += 1
            state["sessions"]["implementation"] += 1
            # Track token estimates (chars//4) and, when the CLI reported them,
            # the REAL measured tokens/cost — kept in separate state slots.
            token_est = state.setdefault("token_estimates", {"input": 0, "output": 0})
            token_est["input"] += prompt_chars // 4
            token_est["output"] += output_chars // 4
            real_in, real_out = usage_tokens(impl_session.usage)
            accumulate_token_usage(state, real_in, real_out, impl_session.cost_usd)
            log(f"  Session tokens: ~{prompt_chars // 4000}k input, ~{output_chars // 4000}k output")
            log_event(
                config, "session.metrics", spec=spec_key, story=story["id"],
                phase="implement", model=impl_model, attempt=attempt,
                tokens_input=real_in, tokens_output=real_out,
                cost_usd=impl_session.cost_usd,
                token_estimate_input=prompt_chars // 4,
                token_estimate_output=output_chars // 4,
            )
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
                log_event(
                    config, "story.implement.failed", severity="critical",
                    spec=spec_key, story=story["id"], attempt=attempt,
                    failure_type=f_type, permanent=True, reason=impl_output[:200],
                )
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
                log_event(
                    config, "story.implement.failed", severity="warning",
                    spec=spec_key, story=story["id"], attempt=attempt,
                    failure_type=f_type, permanent=False, reason=impl_output[:200],
                )
                # Delete the failed attempt branch (no diff to capture on session error)
                delete_attempt_branch(project_dir, feature_branch, attempt_branch)
                clean_result_files(project_dir)
                continue

            # --- Read implementation result from file ---
            impl_result, impl_error = read_implementation_result(project_dir)
            if impl_error:
                log(f"  Implementation result: {impl_error}")
            log_event(
                config, "story.implement.completed", spec=spec_key, story=story["id"],
                attempt=attempt,
                status=(impl_result or {}).get("status", "unknown"),
                has_result=impl_result is not None,
            )

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
            verify_session = run_claude_session(
                verify_prompt, project_dir, timeout=verify_timeout, model=verify_model
            )
            verify_output = verify_session.output
            verify_output_chars = len(verify_output)

            state["sessions"]["total"] += 1
            state["sessions"]["verification"] += 1
            token_est["input"] += verify_prompt_chars // 4
            token_est["output"] += verify_output_chars // 4
            v_real_in, v_real_out = usage_tokens(verify_session.usage)
            accumulate_token_usage(state, v_real_in, v_real_out, verify_session.cost_usd)
            log(f"  Session tokens: ~{verify_prompt_chars // 4000}k input, ~{verify_output_chars // 4000}k output")
            log_event(
                config, "session.metrics", spec=spec_key, story=story["id"],
                phase="verify", model=verify_model, attempt=attempt,
                tokens_input=v_real_in, tokens_output=v_real_out,
                cost_usd=verify_session.cost_usd,
                token_estimate_input=verify_prompt_chars // 4,
                token_estimate_output=verify_output_chars // 4,
            )
            save_state(state, config)

            # --- Check for verification session errors ---
            if is_session_error(verify_output):
                f_type = classify_failure("", verify_output, None)
                log(f"  Verification session error [{f_type}]: {verify_output[:200]}")
                log_event(
                    config, "story.verify.error", severity="warning",
                    spec=spec_key, story=story["id"], attempt=attempt,
                    failure_type=f_type, reason=verify_output[:200],
                )
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
                log_event(
                    config, "story.verify.error", severity="warning",
                    spec=spec_key, story=story["id"], attempt=attempt,
                    failure_type="VERIFY_RESULT_INVALID", reason=str(verify_error)[:200],
                )
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
                log_event(
                    config, "story.verify.passed", spec=spec_key, story=story["id"],
                    actor={"kind": "agent", "id": "story-verifier", "model": verify_model},
                    attempt=attempt, verdict=verdict["verdict"],
                    warnings_count=len(verdict_warnings),
                )
                # Merge attempt branch into feature branch
                log_event(
                    config, "merge.attempted", spec=spec_key, story=story["id"],
                    attempt=attempt, target_branch=feature_branch,
                    attempt_branch=attempt_branch,
                )
                merge_ok = merge_attempt_branch(project_dir, feature_branch, attempt_branch)
                if not merge_ok:
                    log(f"  Merge conflict — aborting merge, will retry implementation.")
                    log_event(
                        config, "merge.failed", severity="warning",
                        spec=spec_key, story=story["id"], attempt=attempt,
                        target_branch=feature_branch, reason="conflict",
                    )
                    # warn-only: the stuck-state check right below raises if
                    # the abort didn't actually clean up.
                    run_git(["merge", "--abort"], project_dir, warn=True)
                    is_clean, stuck = check_git_clean_recovery(project_dir)
                    if not is_clean:
                        raise GitRecoveryFailed(
                            f"`git merge --abort` did not clean up after merge conflict — repo stuck in {stuck} state. "
                            f"Cannot safely retry. Manual intervention required: cd {project_dir} && git status"
                        )
                    log_event(
                        config, "recovery.succeeded", spec=spec_key, story=story["id"],
                        attempt=attempt, recovered_from="merge_conflict",
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
                # Best-effort: the result commit is research provenance (which
                # code this spec produced), never allowed to break the merge.
                try:
                    merge_head = get_head_commit(project_dir)
                except Exception:
                    merge_head = None
                log_event(
                    config, "merge.landed", spec=spec_key, story=story["id"],
                    attempt=attempt, target_branch=feature_branch, verified=True,
                    commit=merge_head,
                )
                # Run cross-story regression check
                reg_passed, reg_msg = run_regression_check(
                    project_dir, state, story["id"], fail_fast_test, spec_key
                )
                if not reg_passed:
                    log(f"  REGRESSION detected after merging {story['id']}!")
                    log(f"  {reg_msg[:300]}")
                    # Revert the merge to keep feature branch clean
                    if not merge_head:
                        merge_head = get_head_commit(project_dir)
                    # warn-only: the returncode is inspected manually below,
                    # escalating to GitRecoveryFailed with remediation steps.
                    revert_result = run_git(["revert", "--no-edit", merge_head], project_dir, warn=True)
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
                    # A regression is a RETRYABLE failure, like every other gate
                    # in this loop — not a terminal one. Through 2.9.x this path
                    # called sys.exit(1) instead, which burned the entire guarded
                    # retry budget on the first failure and tripped the
                    # `orchestrator-exited` supervisor stop in entry.py's finally
                    # block. One flaky cross-story test therefore ended the whole
                    # run rather than costing a single attempt. Falling through to
                    # `continue` hands control back to the retry-limit check at the
                    # top of the loop, which already does the right thing once
                    # retries are genuinely exhausted: pause for review in guarded
                    # mode, fail terminally in autonomous.
                    #
                    # Deliberately NOT setting state["status"] = "failed" here —
                    # the story is still in flight, and a "failed" run status mid
                    # retry misreports the run to /kit-tools:execution-status.
                    learnings.append(f"Regression after merge: {reg_msg[:200]}")
                    log_story_failure(
                        story, attempt, config, f"Regression: {reg_msg[:500]}", learnings
                    )
                    update_state_story(
                        state, story["id"], "retrying", attempt,
                        learnings,
                        f"Regression detected: {reg_msg[:500]}",
                        spec_key=spec_key, failure_type="REGRESSION"
                    )
                    save_state(state, config)
                    log_event(
                        config, "regression.detected", severity="warning",
                        spec=spec_key, story=story["id"], attempt=attempt,
                        reason=reg_msg[:200], retrying=True,
                    )
                    write_notification(
                        config, "regression_detected",
                        f"Regression detected after {story['id']}",
                        f"{story['id']}: {reg_msg[:200]} — merge reverted, "
                        f"retrying (attempt {attempt}).",
                        severity="warning",
                    )
                    # The same cleanup every other retryable failure performs:
                    # capture the attempt diff as retry context, then delete the
                    # attempt branch. The old terminal path did neither, so
                    # omitting them now would leak one branch per regression and
                    # deprive the next attempt of the diff it learns from.
                    attempt_diff = delete_attempt_branch(
                        project_dir, feature_branch, attempt_branch
                    )
                    _store_attempt_diff(state, story["id"], attempt_diff, spec_key)
                    save_state(state, config)
                    clean_result_files(project_dir)
                    write_health_snapshot(
                        config, state, story["id"], attempt, event="attempt_failed"
                    )
                    continue
                elif "Skipped" not in reg_msg:
                    log(f"  Regression check: {reg_msg}")

                # Persist result_commit only now that the merge has survived the
                # regression gate — writing it right after merge.landed would
                # leave a stale value (pointing at a since-reverted commit) on
                # the regression/revert/retry path above. Best-effort:
                # research provenance must never break the merge.
                if merge_head:
                    try:
                        if spec_key is not None:
                            state["specs"][spec_key]["result_commit"] = merge_head
                        else:
                            state["result_commit"] = merge_head
                    except Exception:
                        pass

                # Update feature spec checkboxes on the feature branch
                if update_spec_checkboxes(spec_path, story["id"]):
                    log(f"  Updated feature spec checkboxes for {story['id']}")
                    run_git(["add", spec_path], project_dir, warn=True)
                    # check=True raises: an uncommitted spec edit left behind
                    # here is exactly the dirty-tracked-file trigger behind the
                    # 2.6.4 silent-merge loss — fail loudly at the proximate
                    # cause instead of one story later.
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
                log_event(
                    config, "story.completed", spec=spec_key, story=story["id"],
                    attempt=attempt, warnings_count=len(verdict_warnings),
                    files_changed_count=len(changed_file_list),
                )
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
                log_event(
                    config, "story.verify.rejected", severity="warning",
                    spec=spec_key, story=story["id"],
                    actor={"kind": "agent", "id": "story-verifier", "model": verify_model},
                    attempt=attempt, failure_type=f_type,
                    has_feedback=bool(verdict.get("recommendations")),
                    reason=str(failure_details)[:200],
                )
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


