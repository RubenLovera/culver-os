#!/usr/bin/env python3
"""
evening-review.py — Auto-fills Evening Review section in today's daily note using LLM.
Analyzes completed tasks, top 3 priorities, and habits to generate the review.

Runs daily at 04:00 UTC via systemd timer.

Env vars (from .env.admin):
  GEMINI_API_KEY        — LLM key
  CULVER_OS_DIR         — base VPS directory
  PERSONAL_VAULT_PATH   — local path to personal vault clone
  DAILY_NOTES_SUBDIR    — subdirectory for daily notes (default: Daily Notes)
  USER_NAME             — user's name for personalized prompt
  USER_TIMEZONE         — timezone (default: America/Los_Angeles)
"""

import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(".env.admin")

CULVER_OS_DIR = Path(os.environ.get("CULVER_OS_DIR", "/root/culver-os"))
sys.path.insert(0, str(CULVER_OS_DIR))

from tools.vault_writer import escribir_en_vault_sync

TZ = ZoneInfo(os.environ.get("USER_TIMEZONE", "America/Los_Angeles"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
USER_NAME      = os.environ.get("USER_NAME", "the user")

PERSONAL_VAULT = Path(os.environ.get("PERSONAL_VAULT_PATH",
                                     str(CULVER_OS_DIR / "vaults" / "personal-vault")))
DAILY_NOTES_SUBDIR = os.environ.get("DAILY_NOTES_SUBDIR", "Daily Notes")
DAILY_NOTES_DIR    = PERSONAL_VAULT / DAILY_NOTES_SUBDIR
PERSONAL_VAULT_REPO = "personal-vault"


def log(msg: str):
    print(msg, flush=True)


def git_pull(vault_path: Path, name: str):
    try:
        r = subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=vault_path, capture_output=True, text=True, timeout=30
        )
        log(f"[evening-review] git pull {name}: {'OK' if r.returncode == 0 else r.stderr[:100]}")
    except Exception as e:
        log(f"[evening-review] ⚠️ git pull {name} failed: {e}")


def already_filled(content: str) -> bool:
    """Returns True if Evening Review already has real content (≥4 lines)."""
    er_start = content.find("## 🌙 Evening Review")
    if er_start == -1:
        return False
    er_section = content[er_start:]
    filled_lines = [
        l for l in er_section.split("\n")[1:20]
        if l.strip()
        and not l.strip().startswith("#")
        and l.strip() != "-"
        and "?" not in l
    ]
    return len(filled_lines) >= 4


def call_gemini(prompt: str, retries: int = 3) -> str:
    from google import genai
    from google.genai import types as gt

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=gt.GenerateContentConfig(temperature=0.3, max_output_tokens=1024),
            )
            return response.text or ""
        except Exception as e:
            wait = [30, 60, 120][attempt]
            log(f"[evening-review] ⚠️ Gemini attempt {attempt + 1}: {e} — retry {wait}s")
            if attempt < retries - 1:
                time.sleep(wait)
    return ""


def generate_evening_review(content: str, today_str: str) -> str:
    prompt = f"""Analyze this daily note for {USER_NAME} and pre-fill the Evening Review section.

DATE: {today_str}
NOTE:
===
{content[:3500]}
===

YOUR TASK:
1. From task sections: count completed `- [x]` and pending `- [ ]` items per area
2. From Top 3 Priorities: check how many were completed
3. From Habits section: count the `- [x]` checkboxes
4. Generate suggestions based on real evidence from the note

RESPOND ONLY with the Evening Review block ready to replace, exactly in this format:

## 🌙 Evening Review
- What went well today? [specific suggestion based on completed tasks — or leave blank]
- What's still pending? [2-3 key pending tasks — or leave blank]
- What did I learn today?
- One thing I'd do differently tomorrow: [suggestion based on the day — or leave blank]
- Habits completed: N/5
- Energy level (1-10):
- Tomorrow I want to:

RULES:
- Do not invent data. If there's not enough info, leave the field blank
- Habits: count the `- [x]` in the Habits section and write N/5
- Only the block. No additional explanations."""

    return call_gemini(prompt)


def main():
    if not GEMINI_API_KEY:
        log("[evening-review] ❌ GEMINI_API_KEY not found")
        sys.exit(1)

    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    log(f"[evening-review] {now.strftime('%Y-%m-%d %H:%M')} ({TZ})")

    git_pull(PERSONAL_VAULT, "personal-vault")

    note_path = DAILY_NOTES_DIR / f"{today_str}.md"
    if not note_path.exists():
        log(f"[evening-review] Note {today_str}.md not found — skipping.")
        sys.exit(0)

    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception as e:
        log(f"[evening-review] ❌ Error reading note: {e}")
        sys.exit(1)

    log(f"[evening-review] Note found: {len(content)} chars")

    if already_filled(content):
        log("[evening-review] Evening Review already has content — skipping.")
        sys.exit(0)

    log("[evening-review] Generating Evening Review with Gemini...")
    er_text = generate_evening_review(content, today_str)

    if not er_text or len(er_text) < 50:
        log("[evening-review] ❌ Gemini returned empty or too-short response")
        sys.exit(1)

    match = re.search(r"## 🌙 Evening Review.*", er_text, re.DOTALL)
    er_clean = match.group(0).strip() if match else er_text.strip()

    archivo = f"{DAILY_NOTES_SUBDIR}/{today_str}.md"
    ok = escribir_en_vault_sync(
        PERSONAL_VAULT_REPO, archivo, er_clean,
        "🌙 Evening Review", "actualizar", "evening-review"
    )

    if ok:
        log(f"[evening-review] ✅ Evening Review updated in {today_str}.md")
    else:
        log("[evening-review] ❌ vault_writer failed to update")
        sys.exit(1)


if __name__ == "__main__":
    main()
