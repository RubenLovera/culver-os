"""
daily-note.py — Creates today's daily note in the personal vault.

Reads config from .env.admin, uses the daily-note.md template.
Skips if note already exists for today.
Runs via systemd timer daily at 11:55 UTC.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env.admin"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.vault_writer import escribir_en_vault_sync


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)


def build_note_content(date_str: str, config: dict) -> str:
    template_path = Path(__file__).parent.parent / "_templates" / "daily-note.md"
    template = template_path.read_text(encoding="utf-8")

    # Build project sections
    projects = config.get("projects", [])
    project_sections = "\n".join(
        f"### {p['name']}\n- \n" for p in projects
    ) if projects else "- \n"

    # Build habit checkboxes
    habits = config.get("daily_note", {}).get("habits", [])
    habit_checkboxes = "\n".join(
        f"- [ ] {h}" for h in habits
    ) if habits else "- [ ] "

    content = template.replace("{{DATE}}", date_str)
    content = content.replace("{{PROJECT_SECTIONS}}", project_sections)
    content = content.replace("{{HABIT_CHECKBOXES}}", habit_checkboxes)
    return content


def main():
    config = load_config()
    tz_name = config.get("user", {}).get("timezone", "UTC")

    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.utcnow()

    date_str = now.strftime("%Y-%m-%d")
    daily_dir = config.get("personal_vault", {}).get("daily_notes_subdir", "Daily Notes")
    file_path = f"{daily_dir}/{date_str}.md"

    content = build_note_content(date_str, config)
    result = escribir_en_vault_sync(
        vault="personal",
        archivo=file_path,
        contenido=content,
        modo="crear",
        agente="daily-note",
    )

    if result:
        print(f"[daily-note] ✅ created {file_path}")
    else:
        print(f"[daily-note] ⏭ skipped — {file_path} already exists or write failed")


if __name__ == "__main__":
    main()
