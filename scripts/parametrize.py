#!/usr/bin/env python3
"""
parametrize.py — Sustituye {{PLACEHOLDERS}} en archivos del framework con
los valores del config.json del usuario.

Recorre agents/, scripts/, systemd/, _templates/ y reemplaza in-place.

Uso:
  python3 scripts/parametrize.py --config ~/.culver/config.json --dir ~/culver-os-myname/
"""

import argparse
import json
import os
import re
from pathlib import Path


EXTENSIONS = {".py", ".md", ".sh", ".service", ".timer", ".template", ".yml", ".yaml", ".json"}
SKIP_FILES = {"config.template.json", "parametrize.py", "generate_env.py"}
SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def build_replacements(config: dict) -> dict:
    user = config.get("user", {})
    agent = config.get("agent", {})
    vps = config.get("vps", {})
    telegram = config.get("telegram", {})
    bots = telegram.get("bots", {})
    admin_bot = bots.get("admin", {})
    github = config.get("github", {})
    llm = config.get("llm", {})
    obsidian = config.get("obsidian", {})
    projects = config.get("projects", [{}])
    daily = config.get("daily_note", {})
    habits = daily.get("habits", [])
    sections = daily.get("sections", [])

    replacements = {
        "USER_NAME": user.get("name", ""),
        "TIMEZONE": user.get("timezone", "America/Los_Angeles"),
        "EMAIL": user.get("email", ""),
        "AGENT_NAME": agent.get("name", ""),
        "BRAIN_NAME": agent.get("brain_name", ""),
        "VPS_IP": vps.get("ip", ""),
        "SSH_KEY_PATH": vps.get("ssh_key", "~/.ssh/id_rsa"),
        "CULVER_OS_DIR": vps.get("culver_os_dir", "/root/culver-os"),
        "GROUP_ID": str(telegram.get("group_id", "")),
        "ADMIN_BOT_TOKEN": admin_bot.get("token", ""),
        "ADMIN_THREAD_ID": str(admin_bot.get("thread_id", "")),
        "GITHUB_USERNAME": github.get("username", ""),
        "GITHUB_PAT": github.get("pat", ""),
        "GEMINI_KEY": llm.get("gemini_key", ""),
        "OBSIDIAN_VAULT_PATH": obsidian.get("vault_path", ""),
    }

    for i, project in enumerate(projects[:5], start=1):
        replacements[f"PROJECT_{i}_NAME"] = project.get("name", "")
        replacements[f"PROJECT_{i}_DESC"] = project.get("description", "")

    for i, habit in enumerate(habits[:5], start=1):
        replacements[f"HABIT_{i}"] = habit

    for i, section in enumerate(sections[:5], start=1):
        replacements[f"SECTION_{i}"] = section

    return replacements


def replace_in_file(file_path: Path, replacements: dict) -> int:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return 0

    original = content
    for key, value in replacements.items():
        content = content.replace("{{" + key + "}}", value)

    unreplaced = re.findall(r"\{\{[A-Z_0-9]+\}\}", content)
    if unreplaced:
        print(f"  ⚠️  {file_path.name}: unreplaced placeholders: {set(unreplaced)}")

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        return 1
    return 0


def parametrize(config_path: str, target_dir: str):
    config = load_config(config_path)
    replacements = build_replacements(config)
    target = Path(target_dir)

    modified = 0
    skipped = 0

    for file_path in target.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        if file_path.name in SKIP_FILES:
            continue
        if file_path.suffix not in EXTENSIONS:
            continue

        result = replace_in_file(file_path, replacements)
        if result:
            modified += 1
            print(f"  ✅ {file_path.relative_to(target)}")
        else:
            skipped += 1

    print(f"\n✅ Done: {modified} files modified, {skipped} files unchanged.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to ~/.culver/config.json")
    parser.add_argument("--dir", required=True, help="Target directory to parametrize")
    args = parser.parse_args()
    parametrize(args.config, args.dir)


if __name__ == "__main__":
    main()
