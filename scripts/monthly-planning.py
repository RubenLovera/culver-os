"""
monthly-planning.py — Creates a monthly planning note in the personal vault.

Runs on day 1 of each month at 16:00 UTC.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env.admin"
load_dotenv(env_path)
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.llm import call_llm
from tools.vault_writer import escribir_en_vault_sync


MONTHLY_TEMPLATE = """---
month: {month_label}
date: {date}
type: monthly-planning
---

# {month_label} — Monthly Planning

## Objectives (top 3 this month)

1.
2.
3.

## Projects

{project_sections}

## Habits Target

{habit_targets}

## Monthly Reflection (fill at end of month)

- Biggest win:
- Biggest lesson:
- What to carry forward:

## Notes

"""


def load_config() -> dict:
    with open(Path(__file__).parent.parent / "config.json") as f:
        return json.load(f)


def main():
    config = load_config()
    tz_name = config.get("user", {}).get("timezone", "UTC")

    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now(timezone.utc)

    month_label = now.strftime("%B %Y")
    date_str = now.strftime("%Y-%m-%d")

    projects = config.get("projects", [])
    project_sections = "\n".join(
        f"### {p['name']}\n- This month's goal:\n- Key actions:\n" for p in projects
    ) if projects else "- \n"

    habits = config.get("daily_note", {}).get("habits", [])
    habit_targets = "\n".join(
        f"- {h}: __ / {now.day + (30 - now.day)} days"  # approximate month length
        for h in habits
    ) if habits else "- "

    content = MONTHLY_TEMPLATE.format(
        month_label=month_label,
        date=date_str,
        project_sections=project_sections,
        habit_targets=habit_targets,
    )

    # Store in personal vault under Monthly Reviews/
    file_path = f"Monthly Reviews/{now.strftime('%Y-%m')}-monthly.md"

    result = escribir_en_vault_sync(
        vault="personal",
        archivo=file_path,
        contenido=content,
        modo="crear",
        agente="monthly-planning",
    )
    print(f"[monthly-planning] {'✅' if result else '⏭'} {file_path}")


if __name__ == "__main__":
    main()
