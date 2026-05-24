#!/usr/bin/env python3
"""
Framework Smoke Test — imports + config loading.
No credentials, no VPS, no ChromaDB required.
Run locally before deploying to VPS.

Usage:
    python3 tests/smoke_test.py
"""
import ast
import importlib.util
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

RESULTS = []

# VPS-only packages that won't be installed locally
_VPS_ONLY = {"chromadb"}


def ok(name):
    RESULTS.append(("OK", name))


def skip(name, reason):
    RESULTS.append(("SKIP", f"{name}: {reason}"))


def fail(name, err):
    RESULTS.append(("FAIL", f"{name}: {err}"))


def _is_vps_only_error(err: Exception) -> bool:
    """True if the error is just a missing VPS-only package."""
    msg = str(err)
    return any(pkg in msg for pkg in _VPS_ONLY)


def _load_module(path: Path):
    """Load a Python module from a file path without importing its dependencies."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- 1. Tool imports ---

def test_tool_imports():
    """Tools must import cleanly — ChromaDB client is lazy, no connection needed."""
    tools = [
        "tools.paperclip",
        "tools.obsidian",
        "tools.daily_note",
        "tools.voice",
        "tools.vault_writer",
        "tools.brain",
        "tools.memory",
        "tools.brain_index_incremental",
    ]
    for mod in tools:
        try:
            __import__(mod)
            ok(f"import {mod}")
        except Exception as e:
            if _is_vps_only_error(e):
                skip(f"import {mod}", "chromadb — VPS-only dependency")
            else:
                fail(f"import {mod}", e)


# --- 2. LLM wrapper imports ---

def test_llm_imports():
    llm_mods = [
        "tools.llm.gemini",
        "tools.llm.claude",
        "tools.llm.openai",
    ]
    for mod in llm_mods:
        try:
            __import__(mod)
            ok(f"import {mod}")
        except Exception as e:
            fail(f"import {mod}", e)


# --- 3. Connector imports + registry ---

def test_connector_imports():
    """Connectors must import cleanly with no credentials required."""
    connector_mods = [
        "connectors.base",
        "connectors.obsidian_sync",
        "connectors.github",
        "connectors.notion",
        "connectors.granola",
    ]
    for mod in connector_mods:
        try:
            __import__(mod)
            ok(f"import {mod}")
        except Exception as e:
            fail(f"import {mod}", e)

    # REGISTRY must contain all expected connectors
    try:
        from connectors import REGISTRY
        expected = {"obsidian_sync", "github", "notion", "granola"}
        for name in expected:
            if name in REGISTRY:
                ok(f"connectors.REGISTRY['{name}']")
            else:
                fail(f"connectors.REGISTRY['{name}']", "missing from REGISTRY")
    except Exception as e:
        fail("connectors.REGISTRY", e)


# --- 5. Agent syntax ---

def test_agent_syntax():
    """Agents need env vars to import — check syntax only via ast.parse."""
    agents_dir = REPO_ROOT / "agents"
    for py_file in sorted(agents_dir.glob("*.py")):
        try:
            ast.parse(py_file.read_text())
            ok(f"syntax agents/{py_file.name}")
        except SyntaxError as e:
            fail(f"syntax agents/{py_file.name}", e)


# --- 6. Script syntax ---

def test_script_syntax():
    scripts_dir = REPO_ROOT / "scripts"
    for py_file in sorted(scripts_dir.glob("*.py")):
        try:
            ast.parse(py_file.read_text())
            ok(f"syntax scripts/{py_file.name}")
        except SyntaxError as e:
            fail(f"syntax scripts/{py_file.name}", e)


# --- 7. config.template.json ---

def test_config_template():
    config_path = REPO_ROOT / "config.template.json"
    try:
        config = json.loads(config_path.read_text())
        ok("config.template.json loads")
    except Exception as e:
        fail("config.template.json loads", e)
        return

    required = [
        "user", "agent", "projects", "daily_note",
        "personal_vault", "agent_vault", "llm", "telegram", "github",
    ]
    for key in required:
        if key in config:
            ok(f"config.template.json key '{key}'")
        else:
            fail(f"config.template.json key '{key}'", "missing")

    # Verify placeholder format — no key should have an empty string
    def has_placeholders(obj, path=""):
        issues = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                issues += has_placeholders(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                issues += has_placeholders(v, f"{path}[{i}]")
        elif isinstance(obj, str) and obj == "":
            issues.append(path)
        return issues

    empty_vals = has_placeholders(config)
    if empty_vals:
        fail("config.template.json no empty values", f"empty: {empty_vals[:3]}")
    else:
        ok("config.template.json no empty values")


# --- 8. generate_env.py ---

def test_generate_env():
    script = REPO_ROOT / "scripts" / "generate_env.py"
    try:
        mod = _load_module(script)
        if hasattr(mod, "main"):
            ok("generate_env.py has main()")
        else:
            fail("generate_env.py", "missing main()")
        # Verify both env generators exist
        for fn in ("generate_admin_env", "generate_diario_env"):
            if hasattr(mod, fn):
                ok(f"generate_env.py has {fn}()")
            else:
                fail(f"generate_env.py", f"missing {fn}()")
    except Exception as e:
        fail("generate_env.py", e)


# --- 9. generate_timers.py — TIMERS count ---

def test_generate_timers():
    script = REPO_ROOT / "scripts" / "generate_timers.py"
    try:
        mod = _load_module(script)
        count = len(mod.TIMERS)
        if count == 15:
            ok(f"generate_timers.py TIMERS = {count}")
        else:
            fail("generate_timers.py TIMERS count", f"expected 15, got {count}")
    except Exception as e:
        fail("generate_timers.py", e)


# --- 10. systemd templates ---

def test_systemd_templates():
    systemd_dir = REPO_ROOT / "systemd"
    templates = sorted(systemd_dir.glob("*.template"))
    count = len(templates)
    # 15 timer pairs (service + timer) + 1 bot service = 31
    if count == 31:
        ok(f"systemd templates count = {count}")
    else:
        fail("systemd templates count", f"expected 31, got {count}")

    # Each timer in TIMERS should have both .service.template and .timer.template
    names = {t.name for t in templates}
    timer_names = [
        "log-rotate", "daily-note", "vault-ingest", "vault-health",
        "obsidian-brain-sync", "status-operativo-wed", "status-operativo-sun",
        "weekly-planning", "weekly-fill", "weekly-digest", "perfil-identidad",
        "monthly-planning", "automation-ideas", "evening-review", "vault-brain-sync",
    ]
    for name in timer_names:
        for suffix in ("service", "timer"):
            fname = f"{name}.{suffix}.template"
            if fname in names:
                ok(f"systemd/{fname}")
            else:
                fail(f"systemd/{fname}", "missing")


# --- Runner ---

def main():
    print("CulverOS Framework — Smoke Test")
    print("=" * 40)
    print("(no credentials required)\n")

    test_tool_imports()
    test_llm_imports()
    test_connector_imports()
    test_agent_syntax()
    test_script_syntax()
    test_config_template()
    test_generate_env()
    test_generate_timers()
    test_systemd_templates()

    print()
    for status, name in RESULTS:
        if status == "OK":
            marker = "[OK]  "
        elif status == "SKIP":
            marker = "[SKIP] "
        else:
            marker = "[FAIL] "
        print(f"{marker} {name}")

    failures = [r for r in RESULTS if r[0] == "FAIL"]
    skips = [r for r in RESULTS if r[0] == "SKIP"]
    total = len(RESULTS)
    passed = total - len(failures) - len(skips)
    print(f"\n{passed}/{total - len(skips)} tests passed  ({len(skips)} skipped — VPS-only)")

    if failures:
        print("\nFailures:")
        for _, name in failures:
            print(f"  - {name}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
