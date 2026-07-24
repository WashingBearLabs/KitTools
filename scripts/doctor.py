#!/usr/bin/env python3
"""KitTools doctor — plugin self-integrity and environment diagnostics.

Verifies that the installed plugin is internally consistent (every agent a
skill references exists, agent `required_tokens` match the tokens actually
used in their bodies, hook scripts registered in the manifest are present and
compile, the orchestrator package compiles, registry.py answers its CLI) and
that the host environment can run it (python3, PyYAML, git; tmux/gh for
autonomous execution). With ``--project``, also runs light project-level
checks (worktree.yaml contract, .gitignore block, configured project hooks).

Run by the `/kit-tools:doctor` skill, and as the final verification step of
`/kit-tools:init-project`. All findings are advisory — exit codes signal
severity, nothing here blocks a workflow.

Usage:
    python3 doctor.py [--project DIR] [--json]

Exit codes:
    0 — healthy (info-level findings only)
    1 — warnings found
    2 — errors found (or doctor itself could not run)
"""
from __future__ import annotations

import json
import os
import py_compile
import re
import shutil
import subprocess
import sys

try:
    import yaml  # PyYAML — required by the orchestrator, optional for doctor
except ImportError:
    yaml = None

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_TOKEN_PATTERN = re.compile(r"\{\{([A-Z][A-Z0-9_]+)\}\}")
_FRONTMATTER_PATTERN = re.compile(r"\A\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Schema/reference docs that live in agents/ but are not interpolated agents.
_NON_AGENT_FILES = {"FINDING_SCHEMA.md"}

findings: list[dict] = []


def add(level: str, check: str, message: str, remediation: str = "") -> None:
    entry = {"level": level, "check": check, "message": message}
    if remediation:
        entry["remediation"] = remediation
    findings.append(entry)


def _read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter; regex fallback for `required_tokens` when
    PyYAML is unavailable (good enough for the drift check)."""
    m = _FRONTMATTER_PATTERN.match(content)
    if not m:
        return {}
    fm_text = m.group(1)
    if yaml is not None:
        try:
            fm = yaml.safe_load(fm_text)
            return fm if isinstance(fm, dict) else {}
        except yaml.YAMLError:
            return {}
    fm: dict = {}
    tokens_match = re.search(
        r"^required_tokens:\s*\n((?:\s*-\s+\S+\s*\n?)+)", fm_text, re.MULTILINE
    )
    if tokens_match:
        fm["required_tokens"] = re.findall(r"-\s+([A-Z0-9_]+)", tokens_match.group(1))
    return fm


def _frontmatter_body(content: str) -> str:
    m = _FRONTMATTER_PATTERN.match(content)
    return content[m.end():] if m else content


# --- Plugin integrity checks ------------------------------------------------


def check_manifest() -> dict:
    """Manifest parses; returns it (empty dict on failure) for later checks."""
    path = os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json")
    content = _read(path)
    if content is None:
        add("error", "manifest", f"Missing manifest: {path}")
        return {}
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError as e:
        add("error", "manifest", f"plugin.json does not parse: {e}")
        return {}
    if not manifest.get("version"):
        add("warning", "manifest", "plugin.json has no version field")
    else:
        add("info", "manifest", f"plugin.json OK (version {manifest['version']})")
    return manifest


def check_hooks(manifest: dict) -> None:
    """Every hook command in the manifest resolves to a real file; every
    hooks/*.py compiles."""
    registered: set[str] = set()
    for event, entries in (manifest.get("hooks") or {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                m = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+\.py)", cmd)
                if not m:
                    add("warning", "hooks",
                        f"{event}: unrecognized hook command shape: {cmd!r}")
                    continue
                rel = m.group(1)
                registered.add(rel)
                if not os.path.exists(os.path.join(PLUGIN_ROOT, rel)):
                    add("error", "hooks",
                        f"{event}: registered hook script missing: {rel}")

    hooks_dir = os.path.join(PLUGIN_ROOT, "hooks")
    compiled = failed = 0
    for name in sorted(os.listdir(hooks_dir)) if os.path.isdir(hooks_dir) else []:
        if not name.endswith(".py"):
            continue
        try:
            py_compile.compile(os.path.join(hooks_dir, name), doraise=True)
            compiled += 1
        except py_compile.PyCompileError as e:
            failed += 1
            add("error", "hooks", f"hooks/{name} does not compile: {e.msg}")
    if not failed:
        add("info", "hooks",
            f"{compiled} hook scripts compile; "
            f"{len(registered)} registered in the manifest")


def check_skill_references() -> None:
    """Every agents/*.md, scripts/*.py, and hooks/*.py path mentioned by a
    skill exists on disk. Catches the rename-the-agent-forget-the-skill drift."""
    skills_dir = os.path.join(PLUGIN_ROOT, "skills")
    referenced: dict[str, set[str]] = {}  # rel path -> skills that mention it
    missing_skill_md = []
    for skill in sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []:
        skill_path = os.path.join(skills_dir, skill)
        if not os.path.isdir(skill_path):
            continue
        if not os.path.exists(os.path.join(skill_path, "SKILL.md")):
            missing_skill_md.append(skill)
            continue
        for name in os.listdir(skill_path):
            if not name.endswith(".md"):
                continue
            content = _read(os.path.join(skill_path, name)) or ""
            for pattern in (
                r"\b(agents/[A-Za-z0-9_-]+\.md)",
                r"\b(scripts/[A-Za-z0-9_/-]+\.py)",
                r"\b(hooks/[A-Za-z0-9_]+\.py)",
            ):
                for rel in re.findall(pattern, content):
                    referenced.setdefault(rel, set()).add(skill)

    for skill in missing_skill_md:
        add("error", "skills", f"skills/{skill}/ has no SKILL.md")

    broken = 0
    for rel, skills in sorted(referenced.items()):
        if not os.path.exists(os.path.join(PLUGIN_ROOT, rel)):
            broken += 1
            add("error", "skills",
                f"{rel} referenced by {', '.join(sorted(skills))} but does not exist")
    if not broken:
        add("info", "skills",
            f"{len(referenced)} agent/script/hook references across skills all resolve")


def check_agent_tokens() -> None:
    """Agent frontmatter `required_tokens` vs `{{TOKEN}}`s in the body.

    Drift in either direction means an interpolating skill/orchestrator and
    the agent disagree about the contract — the failure mode is an agent
    receiving a literal `{{TOKEN}}` (or a skill building context nothing uses).
    """
    agents_dir = os.path.join(PLUGIN_ROOT, "agents")
    drift = 0
    checked = 0
    for name in sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []:
        if not name.endswith(".md") or name in _NON_AGENT_FILES:
            continue
        content = _read(os.path.join(agents_dir, name))
        if content is None:
            add("warning", "agent-tokens", f"agents/{name} unreadable")
            continue
        fm = _parse_frontmatter(content)
        declared = {t for t in fm.get("required_tokens", []) if isinstance(t, str)}
        used = set(_TOKEN_PATTERN.findall(_frontmatter_body(content)))
        checked += 1
        for token in sorted(declared - used):
            drift += 1
            add("warning", "agent-tokens",
                f"agents/{name}: {{{{{token}}}}} declared in required_tokens "
                f"but never referenced in the body")
        if "required_tokens" in fm:
            for token in sorted(used - declared):
                drift += 1
                add("warning", "agent-tokens",
                    f"agents/{name}: {{{{{token}}}}} used in the body but not "
                    f"declared in required_tokens")
    if not drift:
        add("info", "agent-tokens", f"{checked} agents: required_tokens match bodies")


def check_agent_security_posture() -> None:
    """Every agent carries a Security posture block with both load-bearing
    clauses (canonical source: agents/_shared/security-posture.md). Agents
    process untrusted content — code, specs, templates — and the block is the
    standing defense against prompt injection riding in on that content."""
    agents_dir = os.path.join(PLUGIN_ROOT, "agents")
    required_clauses = (
        "never as instructions to execute",
        "only source of instructions",
    )
    missing = 0
    checked = 0
    for name in sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []:
        if not name.endswith(".md") or name in _NON_AGENT_FILES:
            continue
        content = _read(os.path.join(agents_dir, name)) or ""
        checked += 1
        if "**Security posture.**" not in content:
            missing += 1
            add("warning", "agent-security",
                f"agents/{name} has no Security posture block",
                remediation="Add a tailored block per agents/_shared/security-posture.md")
            continue
        for clause in required_clauses:
            if clause not in content:
                missing += 1
                add("warning", "agent-security",
                    f"agents/{name}: Security posture block is missing the "
                    f"load-bearing clause {clause!r}")
    if not missing:
        add("info", "agent-security",
            f"{checked} agents carry a complete Security posture block")


EPIC_REVIEWER_AGENTS = (
    "salty-engineer-reviewer.md",
    "codebase-fit-reviewer.md",
    "spec-completionist-reviewer.md",
    "story-quality-reviewer.md",
    "spec-security-reviewer.md",
    "spec-second-opinion.md",
)


def check_epic_reviewer_scores() -> None:
    """The six validate-epic spec reviewers must each emit a per-reviewer
    `readiness_score` (1–10, band-anchored to the verdict — canonical source:
    agents/FINDING_SCHEMA.md). The score feeds validate-epic's gate and the
    run trace; a reviewer that silently drops it loses that signal, and the
    schema doc is where the band rule lives."""
    agents_dir = os.path.join(PLUGIN_ROOT, "agents")
    missing = 0
    checked = 0
    for name in EPIC_REVIEWER_AGENTS:
        content = _read(os.path.join(agents_dir, name))
        if content is None:
            add("warning", "reviewer-scores",
                f"agents/{name} not found — expected a validate-epic spec reviewer")
            missing += 1
            continue
        checked += 1
        if '"readiness_score"' not in content:
            missing += 1
            add("warning", "reviewer-scores",
                f"agents/{name} emits no readiness_score in its output block",
                remediation='Add "readiness_score": <1-10> per agents/FINDING_SCHEMA.md')
    schema = _read(os.path.join(agents_dir, "FINDING_SCHEMA.md")) or ""
    if "readiness_score" not in schema:
        missing += 1
        add("warning", "reviewer-scores",
            "agents/FINDING_SCHEMA.md does not document the readiness_score band rule",
            remediation="Document the 1–10 band anchoring in FINDING_SCHEMA.md")
    if not missing:
        add("info", "reviewer-scores",
            f"{checked} validate-epic reviewers emit a band-anchored readiness_score")


def check_orchestrator() -> None:
    """Every orchestrator module compiles; registry.py answers its CLI and
    implements every subcommand the skills invoke."""
    orch_dir = os.path.join(PLUGIN_ROOT, "scripts", "orchestrator")
    failed = 0
    py_files = []
    for base in (os.path.join(PLUGIN_ROOT, "scripts"), orch_dir):
        if os.path.isdir(base):
            py_files += [os.path.join(base, n) for n in sorted(os.listdir(base))
                         if n.endswith(".py")]
    for path in py_files:
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            failed += 1
            add("error", "orchestrator",
                f"{os.path.relpath(path, PLUGIN_ROOT)} does not compile: {e.msg}")
    if not failed:
        add("info", "orchestrator", f"{len(py_files)} orchestrator scripts compile")

    registry_path = os.path.join(orch_dir, "registry.py")
    registry_src = _read(registry_path)
    if registry_src is None:
        add("error", "orchestrator", "scripts/orchestrator/registry.py is missing")
        return

    # Commands the skills actually call (scanned, not hardcoded) must all be
    # implemented in registry's CLI dispatcher.
    implemented = set(re.findall(r'cmd == "([a-z-]+)"', registry_src))
    implemented |= set(re.findall(r'prog="registry\.py ([a-z-]+)"', registry_src))
    needed: set[str] = set()
    skills_dir = os.path.join(PLUGIN_ROOT, "skills")
    for dirpath, _dirs, names in os.walk(skills_dir):
        for name in names:
            if name.endswith(".md"):
                content = _read(os.path.join(dirpath, name)) or ""
                needed |= set(re.findall(r"registry\.py[\"'`]?\s+([a-z][a-z-]+)\b",
                                         content))
    unimplemented = needed - implemented
    for cmd in sorted(unimplemented):
        add("error", "orchestrator",
            f"skills invoke `registry.py {cmd}` but registry implements no such command")
    if needed and not unimplemented:
        add("info", "orchestrator",
            f"registry.py implements all {len(needed)} subcommands the skills use")

    # And it must actually execute standalone.
    try:
        result = subprocess.run([sys.executable, registry_path],
                                capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            add("error", "orchestrator",
                f"registry.py failed to execute standalone (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}")
    except (OSError, subprocess.TimeoutExpired) as e:
        add("error", "orchestrator", f"registry.py could not be executed: {e}")


def check_environment() -> None:
    if sys.version_info < (3, 9):
        add("error", "environment",
            f"python3 is {sys.version.split()[0]} — orchestrator needs 3.9+")
    else:
        add("info", "environment", f"python3 {sys.version.split()[0]}")
    if yaml is None:
        add("error", "environment",
            "PyYAML not importable — the orchestrator requires it",
            remediation="pip install -r requirements.txt (PyYAML>=6.0)")
    if shutil.which("git") is None:
        add("error", "environment", "git not found on PATH")
    if shutil.which("tmux") is None:
        add("warning", "environment",
            "tmux not found — autonomous/guarded execution needs it "
            "(supervised mode is unaffected)")
    if shutil.which("gh") is None:
        add("info", "environment",
            "gh CLI not found — completion strategies `pr`/`merge` will "
            "degrade to leaving the branch for manual merge")


def check_install_freshness(manifest: dict) -> None:
    """Is this doctor running from the *active* install, at the version the
    user thinks they have?

    `$CLAUDE_PLUGIN_ROOT` can go stale after `/plugin update` (the session
    caches it); `installed_plugins.json` is the source of truth.
    """
    installed = os.path.expanduser("~/.claude/plugins/installed_plugins.json")
    content = _read(installed)
    if content is None:
        add("info", "install", "no installed_plugins.json — skipping freshness check")
        return
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        add("warning", "install", "installed_plugins.json does not parse")
        return

    def _find_record(node) -> dict | None:
        if isinstance(node, dict):
            for key, value in node.items():
                if "kit-tools" in key:
                    candidates = value if isinstance(value, list) else [value]
                    for item in candidates:
                        if isinstance(item, dict) and item.get("installPath"):
                            return item
                found = _find_record(value)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = _find_record(item)
                if found:
                    return found
        return None

    record = _find_record(data)
    if not record:
        add("info", "install", "kit-tools not found in installed_plugins.json "
            "(local/dev install?)")
        return
    here = os.path.realpath(PLUGIN_ROOT)
    active_real = os.path.realpath(os.path.expanduser(record["installPath"]))
    installed_version = record.get("version", "unknown")
    if here == active_real:
        add("info", "install",
            f"running from the active install (version {installed_version})")
    else:
        add("warning", "install",
            f"doctor is running from {here} but the active install is "
            f"{active_real} — a stale $CLAUDE_PLUGIN_ROOT from before a "
            f"/plugin update, or a dev checkout",
            remediation="Restart the Claude Code session (re-resolves the "
                        "plugin root), or ignore if this is intentional dev use")
    manifest_version = manifest.get("version")
    if manifest_version and installed_version not in ("unknown", manifest_version):
        add("warning", "install",
            f"installed plugin is {installed_version} but this checkout's "
            f"manifest says {manifest_version} — the active install is behind",
            remediation="/plugin update kit-tools@washingbearlabs (after the "
                        "release is pushed), then restart the session")


# --- Project-level checks ---------------------------------------------------


def check_project(project_dir: str) -> None:
    kit = os.path.join(project_dir, "kit_tools")
    if not os.path.isdir(kit):
        add("info", "project",
            f"no kit_tools/ in {project_dir} — project checks skipped "
            f"(run /kit-tools:init-project to set up)")
        return

    contract = os.path.join(kit, "worktree.yaml")
    if not os.path.exists(contract):
        add("warning", "project",
            "kit_tools/worktree.yaml missing — autonomous execution will have "
            "no worktree/environment contract",
            remediation="Re-run /kit-tools:init-project (retrofit-safe) to scaffold it")
    elif yaml is not None:
        try:
            loaded = yaml.safe_load(_read(contract) or "") or {}
            if not isinstance(loaded, dict):
                add("warning", "project", "worktree.yaml does not parse to a mapping")
            else:
                known = {"root", "env_bootstrap", "env_link", "path_links",
                         "cleanup_policy"}
                unknown = set(loaded) - known
                if unknown:
                    add("warning", "project",
                        f"worktree.yaml has unrecognized keys: {sorted(unknown)}")
                manifests = ("package.json", "pyproject.toml", "requirements.txt",
                             "Gemfile", "go.mod", "Cargo.toml")
                if not loaded.get("env_bootstrap") and any(
                        os.path.exists(os.path.join(project_dir, m)) for m in manifests):
                    add("warning", "project",
                        "worktree.yaml env_bootstrap is empty but the project has "
                        "a dependency manifest — a fresh worktree won't be runnable "
                        "and verification tests will fail",
                        remediation="Add the install command(s) (e.g. `npm install`, "
                                    "`uv sync`) to env_bootstrap")
                else:
                    add("info", "project", "worktree.yaml parses and looks sane")
        except yaml.YAMLError as e:
            add("warning", "project", f"worktree.yaml does not parse: {e}")

    gitignore = _read(os.path.join(project_dir, ".gitignore")) or ""
    if ".kit/" not in gitignore:
        add("warning", "project",
            ".gitignore is missing the KitTools block (`.kit/` registry + "
            "transient execution state) — a `git add -A` could commit it",
            remediation="python3 <plugin>/scripts/orchestrator/registry.py "
                        "ensure-gitignore")
    else:
        add("info", "project", ".gitignore has the KitTools block")

    project_hooks = os.path.join(kit, "hooks")
    if os.path.isdir(project_hooks):
        bad = 0
        for name in sorted(os.listdir(project_hooks)):
            if name.endswith(".py"):
                try:
                    py_compile.compile(os.path.join(project_hooks, name), doraise=True)
                except py_compile.PyCompileError as e:
                    bad += 1
                    add("error", "project",
                        f"kit_tools/hooks/{name} does not compile: {e.msg}")
        if not bad:
            add("info", "project", "project hook scripts compile")

    _check_model_preferences(kit)

    settings = _read(os.path.join(project_dir, ".claude", "settings.local.json"))
    if settings is not None:
        try:
            json.loads(settings)
            add("info", "project", ".claude/settings.local.json parses")
        except json.JSONDecodeError as e:
            add("warning", "project", f".claude/settings.local.json does not parse: {e}")


_KNOWN_MODEL_ROLES = {
    "implementer", "verifier", "validator", "reviewer",
    "second_opinion", "escalation",
}


def _check_model_preferences(kit: str) -> None:
    """Advisory validation of kit_tools/model_preferences.json (optional file).

    Absence is fine — every role falls back to the built-in default. When
    present, catch the ways it silently misbehaves: unparseable JSON, a
    non-object `models` block, unrecognized role names, and non-string values.
    Model aliases like `sonnet`/`opus`/`haiku` (and full `claude-*` ids) are
    all valid values the `claude --model` CLI accepts, so values are not
    otherwise constrained here.
    """
    path = os.path.join(kit, "model_preferences.json")
    raw = _read(path)
    if raw is None:
        return  # optional file; all roles fall back to their built-in defaults
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        add("warning", "project",
            f"model_preferences.json does not parse: {e}",
            remediation="Fix the JSON or re-run the configure-models skill")
        return
    if not isinstance(data, dict) or not isinstance(data.get("models"), dict):
        add("warning", "project",
            "model_preferences.json has no `models` object — the file is ignored",
            remediation="Re-run the configure-models skill to regenerate it")
        return
    models = data["models"]
    problems = 0
    for role, value in models.items():
        if role not in _KNOWN_MODEL_ROLES:
            problems += 1
            add("warning", "project",
                f"model_preferences.json: unrecognized role '{role}' "
                f"(known roles: {sorted(_KNOWN_MODEL_ROLES)})")
            continue
        if role == "escalation":
            if not isinstance(value, (str, dict)):
                problems += 1
                add("warning", "project",
                    "model_preferences.json: `escalation` must be a policy object "
                    "or a model-id string")
            continue
        if not isinstance(value, str):
            problems += 1
            add("warning", "project",
                f"model_preferences.json: role '{role}' must be a model alias/id "
                f"string (got {type(value).__name__})")
    if not problems:
        add("info", "project", "model_preferences.json parses and roles look valid")


# --- Reporting ---------------------------------------------------------------


def report_human() -> None:
    icons = {"error": "✗", "warning": "⚠", "info": "✓"}
    by_check: dict[str, list[dict]] = {}
    for f in findings:
        by_check.setdefault(f["check"], []).append(f)
    print("KitTools Doctor")
    print(f"Plugin root: {PLUGIN_ROOT}")
    print("=" * 60)
    for check, items in by_check.items():
        print(f"\n[{check}]")
        for f in items:
            print(f"  {icons[f['level']]} {f['message']}")
            if f.get("remediation"):
                print(f"      fix: {f['remediation']}")
    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    print("\n" + "=" * 60)
    print(f"Result: {errors} error(s), {warnings} warning(s)")
    if errors:
        print("Status: UNHEALTHY — fix errors before relying on autonomous execution")
    elif warnings:
        print("Status: OK with warnings")
    else:
        print("Status: HEALTHY")


def main(argv: list[str]) -> int:
    project_dir = None
    as_json = False
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--json":
            as_json = True
        elif arg == "--project":
            if not args:
                print("usage: doctor.py [--project DIR] [--json]", file=sys.stderr)
                return 2
            project_dir = args.pop(0)
        elif arg in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return 2

    manifest = check_manifest()
    check_hooks(manifest)
    check_skill_references()
    check_agent_tokens()
    check_agent_security_posture()
    check_epic_reviewer_scores()
    check_orchestrator()
    check_environment()
    check_install_freshness(manifest)
    if project_dir:
        check_project(os.path.abspath(project_dir))

    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    if as_json:
        print(json.dumps({
            "plugin_root": PLUGIN_ROOT,
            "errors": errors,
            "warnings": warnings,
            "status": "unhealthy" if errors else ("warnings" if warnings else "healthy"),
            "findings": findings,
        }, indent=2))
    else:
        report_human()
    return 2 if errors else (1 if warnings else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
