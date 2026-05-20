#!/usr/bin/env python3
"""
generate_timers.py — Genera los archivos .service y .timer desde templates,
reemplazando {{PLACEHOLDERS}} con los valores del config.json.

En VPS (Linux): escribe en /etc/systemd/system/ y activa los timers.
En local (Mac/Windows): escribe en deploy/output/systemd/ para inspección.

Uso:
  python3 scripts/generate_timers.py ~/.culver/config.json
"""

import json
import platform
import subprocess
import sys
from pathlib import Path


TIMERS = [
    "log-rotate",
    "daily-note",
    "vault-ingest",
    "vault-health",
    "vault-brain-sync",
    "obsidian-brain-sync",
    "automation-ideas",
    "evening-review",
    "status-operativo-wed",
    "status-operativo-sun",
    "weekly-planning",
    "weekly-fill",
    "weekly-digest",
    "perfil-identidad",
    "monthly-planning",
]

IS_LINUX = platform.system() == "Linux"
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def build_replacements(config: dict) -> dict:
    agent = config.get("agent", {})
    vps = config.get("vps", {})
    return {
        "{{AGENT_NAME}}": agent.get("name", "Admin"),
        "{{BRAIN_NAME}}": agent.get("brain_name", "culver"),
        "{{CULVER_OS_DIR}}": vps.get("culver_os_dir", "/root/culver-os"),
    }


def apply_replacements(content: str, replacements: dict) -> str:
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def generate_timers(config_path: str):
    config = load_config(config_path)
    replacements = build_replacements(config)

    # Templates are always in <repo_root>/systemd/ — regardless of culver_os_dir
    templates_dir = REPO_ROOT / "systemd"

    # Output: /etc/systemd/system/ on VPS, deploy/output/systemd/ locally
    if IS_LINUX:
        systemd_dir = Path("/etc/systemd/system")
    else:
        systemd_dir = REPO_ROOT / "deploy" / "output" / "systemd"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ℹ️  Local mode — output: {systemd_dir}\n")

    generated = []

    for timer_name in TIMERS:
        for suffix in ["service", "timer"]:
            template_file = templates_dir / f"{timer_name}.{suffix}.template"
            if not template_file.exists():
                print(f"  ⚠️  Template not found: {template_file.name} — skipping")
                continue

            content = template_file.read_text()
            content = apply_replacements(content, replacements)

            output_file = systemd_dir / f"{timer_name}.{suffix}"
            output_file.write_text(content)
            print(f"  ✅ Generated {output_file.name}")
            generated.append(output_file.name)

    timer_count = len([n for n in generated if n.endswith(".timer")])

    if IS_LINUX:
        print("\n🔄 Reloading systemd daemon...")
        subprocess.run(["systemctl", "daemon-reload"], check=True)

        for name in generated:
            if name.endswith(".timer"):
                subprocess.run(["systemctl", "enable", "--now", name], check=True)
                print(f"  ✅ Enabled and started {name}")

        print(f"\n✅ {timer_count} timers active.")
    else:
        print(f"\n✅ {timer_count} timers generated. Copy to /etc/systemd/system/ on your VPS.")
        print(f"   Files in: {systemd_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_timers.py <config.json>")
        sys.exit(1)
    generate_timers(sys.argv[1])
