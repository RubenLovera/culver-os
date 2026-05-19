"""
weekly-planning.py — Creates a weekly review note in the personal vault.

Runs Sundays at 15:00 UTC.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env.admin"
load_dotenv(env_path)
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.vault_writer import escribir_en_vault_sync


WEEKLY_TEMPLATE = """---
week: {week_label}
date: {date}
type: weekly-review
---

# Week {week_num} — {week_label}

## Reflection

- What were my top 3 wins this week?
  1.
  2.
  3.

- What didn't go as planned?

- Energy level average (1-10):

## Projects

{project_sections}

## Habits

{habit_checkboxes}

## Next Week — Top 3 Priorities

1.
2.
3.

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

    # Week label: Mon–Sun of current week
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    week_num = now.isocalendar()[1]
    date_str = now.strftime("%Y-%m-%d")

    projects = config.get("projects", [])
    project_sections = "\n".join(
        f"### {p['name']}\n- Progress:\n- Next steps:\n" for p in projects
    ) if projects else "- \n"

    habits = config.get("daily_note", {}).get("habits", [])
    habit_checkboxes = "\n".join(f"- [ ] {h}" for h in habits) if habits else "- [ ] "

    content = WEEKLY_TEMPLATE.format(
        week_label=week_label,
        date=date_str,
        week_num=week_num,
        project_sections=project_sections,
        habit_checkboxes=habit_checkboxes,
    )

    weekly_dir = config.get("personal_vault", {}).get("weekly_reviews_subdir", "Weekly Reviews")
    file_path = f"{weekly_dir}/{date_str}-week-{week_num}.md"

    result = escribir_en_vault_sync(
        vault="personal",
        archivo=file_path,
        contenido=content,
        modo="crear",
        agente="weekly-planning",
    )
    print(f"[weekly-planning] {'✅' if result else '⏭'} {file_path}")


if __name__ == "__main__":
    main()
