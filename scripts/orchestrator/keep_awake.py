"""Keep the machine awake for the duration of an autonomous/guarded run.

A long unattended run is useless if the laptop sleeps mid-way and suspends the
tmux orchestrator. When the user opts in (`keep_awake: true` in the execution
config), the orchestrator holds a power assertion that prevents *idle* and
*system* sleep — the display is allowed to sleep, there's no reason to keep the
screen lit. The assertion is released automatically when the orchestrator exits
(the helper process is terminated by the orchestrator's atexit/signal handlers),
so there's nothing for the user to clean up.

Best-effort everywhere: an unavailable inhibitor (Linux without systemd, an
unknown OS, a missing binary) degrades to a logged no-op — never a failed run.
"""
from __future__ import annotations

import platform
import subprocess

from .utils import log


def _inhibitor_command() -> list[str] | None:
    """The OS-appropriate command that holds a sleep assertion while it runs.

    macOS: `caffeinate -i -s` (prevent idle + system sleep; display may sleep).
    Linux: `systemd-inhibit ... sleep infinity` (held while the child runs).
    Anything else: None — no supported inhibitor.
    """
    system = platform.system()
    if system == "Darwin":
        return ["caffeinate", "-i", "-s"]
    if system == "Linux":
        return [
            "systemd-inhibit",
            "--what=idle:sleep",
            "--who=KitTools",
            "--why=autonomous execution",
            "--mode=block",
            "sleep", "infinity",
        ]
    return None


def start_keep_awake(config: dict) -> subprocess.Popen | None:
    """Start a sleep-inhibitor child if `keep_awake` is enabled. Returns the
    process (to terminate on exit) or None when disabled/unavailable. Best-effort."""
    if not config.get("keep_awake"):
        return None
    cmd = _inhibitor_command()
    if cmd is None:
        log(f"  keep_awake requested but unsupported on {platform.system()} — continuing without it.")
        return None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        log(f"  keep_awake: holding a sleep assertion ({cmd[0]}) for this run.")
        return proc
    except (OSError, ValueError) as e:
        # Binary missing (e.g. no systemd-inhibit) or spawn failure — degrade.
        log(f"  keep_awake unavailable ({cmd[0]}: {e}) — continuing without it.")
        return None


def stop_keep_awake(proc: subprocess.Popen | None) -> None:
    """Release the sleep assertion. Best-effort, idempotent — safe to call from
    an atexit/signal handler."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass
