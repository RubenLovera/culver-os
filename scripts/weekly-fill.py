"""
weekly-fill.py — Auto-fills the weekly review with LLM-generated insights.

Reads daily notes from the past 7 days and generates a filled weekly review.
Runs Sundays at 15:20 UTC (after weekly-planning.py creates the skeleton).
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

from tools.llm import call_llm
from tools.vault_writer import escribir_en_vault_sync


def load_config() -> dict:
    with open(Path(__file__).parent.parent / "config.json") as f:
        return json.load(f)


def collect_daily_notes(personal_vault: Path, days: int = 7) -> str:
    daily_dir = personal_vault / "Daily Notes"
    if not daily_dir.exists():
        return "(no daily notes found)"
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    notes = []
    for f in sorted(daily_dir.glob("*.md"), reverse=True)[:days]:
        try:
            date_str = f.stem
            note_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if note_date >= cutoff:
                notes.append(f"### {date_str}\n{f.read_text(encoding='utf-8', errors='ignore')[:600]}")
        except ValueError:
            continue
    return "\n\n".join(notes) if notes else "(no daily notes found)"


def main():
    config = load_config()
    tz_name = config.get("user", {}).get("timezone", "UTC")

    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now(timezone.utc)

    week_num = now.isocalendar()[1]
    date_str = now.strftime("%Y-%m-%d")

    personal_vault = Path(os.environ.get("PERSONAL_VAULT_PATH", ""))
    daily_notes = collect_daily_notes(personal_vault) if personal_vault.exists() else "(vault not available)"

    user_name = config.get("user", {}).get("name", "the user")
    projects = config.get("projects", [])
    projects_list = "\n".join(f"- {p['name']}: {p.get('description', '')}" for p in projects)

    prompt = f"""You are reviewing {user_name}'s week and filling in their weekly review.

Active projects:
{projects_list}

Daily notes from this week:
{daily_notes}

Based on the daily notes, generate a concise weekly summary in Markdown with:

## Reflection

- Top 3 wins this week:
  1. (specific win from the notes)
  2. (specific win from the notes)
  3. (specific win from the notes)

- What didn't go as planned: (honest 1-2 sentences)

- Energy level average: (estimate from mood/tone of notes)

## Highlights de la Semana
(3-5 bullet points: key accomplishments, decisions, or insights)

## Pendientes para la próxima semana
(top 3 items that appeared multiple times or were explicitly flagged)

Write in the same language as the daily notes. Be specific — use actual details from the notes, not generic filler."""

    fill_content = call_llm(prompt)

    weekly_dir = config.get("personal_vault", {}).get("weekly_reviews_subdir", "Weekly Reviews")
    file_path = f"{weekly_dir}/{date_str}-week-{week_num}.md"

    result = escribir_en_vault_sync(
        vault="personal",
        archivo=file_path,
        contenido=fill_content,
        seccion="Reflection",
        modo="actualizar",
        agente="weekly-fill",
    )
    print(f"[weekly-fill] {'✅' if result else '❌'} filled {file_path}")


if __name__ == "__main__":
    main()
