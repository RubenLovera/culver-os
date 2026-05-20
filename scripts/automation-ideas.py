#!/usr/bin/env python3
"""
automation-ideas.py — Generates daily automation ideas per project using LLM.
Reads recent daily notes for context, writes ideas to the personal vault.

Runs daily at 02:01 UTC via systemd timer.

Env vars (from .env.admin):
  GEMINI_API_KEY        — LLM key
  CULVER_OS_DIR         — base VPS directory
  PERSONAL_VAULT_PATH   — local path to personal vault clone
  DAILY_NOTES_SUBDIR    — subdirectory for daily notes (default: Daily Notes)
  AUTO_IDEAS_SUBDIR     — subdirectory for automation ideas (default: Automation Ideas)
  CONFIG_PATH           — path to config.json
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(".env.admin")

CULVER_OS_DIR = Path(os.environ.get("CULVER_OS_DIR", "/root/culver-os"))
sys.path.insert(0, str(CULVER_OS_DIR))

from tools.vault_writer import escribir_en_vault_sync

TZ = ZoneInfo(os.environ.get("USER_TIMEZONE", "America/Los_Angeles"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PERSONAL_VAULT = Path(os.environ.get("PERSONAL_VAULT_PATH",
                                     str(CULVER_OS_DIR / "vaults" / "personal-vault")))
DAILY_NOTES_SUBDIR = os.environ.get("DAILY_NOTES_SUBDIR", "Daily Notes")
AUTO_IDEAS_SUBDIR  = os.environ.get("AUTO_IDEAS_SUBDIR", "Automation Ideas")

DAILY_NOTES_DIR = PERSONAL_VAULT / DAILY_NOTES_SUBDIR
AUTO_IDEAS_DIR  = PERSONAL_VAULT / AUTO_IDEAS_SUBDIR

CONFIG_PATH = os.environ.get("CONFIG_PATH", str(CULVER_OS_DIR / "config.json"))
PERSONAL_VAULT_REPO = "personal-vault"


def log(msg: str):
    print(msg, flush=True)


def load_projects() -> list[tuple[str, str, str]]:
    """Returns list of (slug, name, description) from config.json."""
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        projects = cfg.get("projects", [])
        result = []
        for p in projects:
            name = p.get("name", "")
            slug = name.lower().replace(" ", "-").replace("_", "-")
            desc = p.get("description", name)
            result.append((slug, name, desc))
        return result
    except Exception as e:
        log(f"[automation-ideas] ⚠️ Could not load projects from config: {e}")
        return []


def git_pull(path: Path, name: str):
    try:
        r = subprocess.run(["git", "pull", "--rebase"], cwd=path,
                           capture_output=True, text=True, timeout=30)
        log(f"[automation-ideas] git pull {name}: {'OK' if r.returncode == 0 else r.stderr[:80]}")
    except Exception as e:
        log(f"[automation-ideas] ⚠️ git pull {name}: {e}")


def load_recent_notes(days: int = 7) -> dict:
    today = datetime.now(TZ).date()
    notes = {}
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        p = DAILY_NOTES_DIR / f"{d}.md"
        if p.exists():
            try:
                notes[d] = p.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass
    return notes


def section_exists_today(file_path: Path, today_str: str) -> bool:
    if not file_path.exists():
        return False
    try:
        return f"### {today_str}" in file_path.read_text(encoding="utf-8")
    except Exception:
        return False


def get_ideas_section(file_path: Path) -> str:
    if not file_path.exists():
        return ""
    try:
        content = file_path.read_text(encoding="utf-8")
        match = re.search(r"## 💡 Pending Ideas\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
        return match.group(1).strip() if match else ""
    except Exception:
        return ""


def call_gemini(prompt: str, retries: int = 3) -> str:
    from google import genai
    from google.genai import types as gt

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=gt.GenerateContentConfig(temperature=0.4, max_output_tokens=4096),
            )
            return response.text or ""
        except Exception as e:
            wait = [30, 60, 120][attempt]
            log(f"[automation-ideas] ⚠️ Gemini attempt {attempt + 1}: {e} — retry {wait}s")
            if attempt < retries - 1:
                time.sleep(wait)
    return ""


def generate_ideas(today_str: str, notes_block: str, projects: list) -> str:
    projects_list = "\n".join(f"- {slug}: {desc}" for slug, _, desc in projects)
    slugs = [slug for slug, _, _ in projects]

    slug_blocks = "\n\n".join(
        f"===PROJECT: {slug}===\n[2 ideas]\n===END==="
        for slug in slugs
    )

    prompt = f"""You are an automation ideas generator for a founder's personal productivity system.
Date: {today_str}.

DAILY NOTES (last 7 days):
{notes_block}

TASK: Generate exactly 2 automation ideas per project, based on real patterns from the daily notes.
Look for: repeated tasks, manual work mentioned, frictions in evening reviews, recurring pending items.

Projects:
{projects_list}

RESPONSE FORMAT — use exactly these separators:

{"".join(
    f"""===PROJECT: {slug}===
- [ ] **[Concise title]** — [What it automates, how it works, what problem it solves. Max 2 lines.]
  *Why now? [Context from the daily notes with date — or "General idea" if no specific context.]*

- [ ] **[Concise title]** — [...]
  *Why now? [...]*
===END===

"""
    for slug, _, _ in projects
)}

RULES:
- Concrete and actionable ideas, not generic ones
- If there's no context in the daily notes for a project, generate a general idea anyway
- Exactly 2 ideas per project, no more no less"""

    return call_gemini(prompt)


def parse_ideas(gemini_output: str, projects: list) -> dict:
    ideas = {}
    for slug, _, _ in projects:
        pattern = rf"===PROJECT: {re.escape(slug)}===\n(.*?)===END==="
        match = re.search(pattern, gemini_output, re.DOTALL)
        if match:
            ideas[slug] = match.group(1).strip()
    return ideas


def insert_ideas_into_file(file_path: Path, slug: str, name: str,
                            today_str: str, new_ideas: str) -> bool:
    existing_section = get_ideas_section(file_path)
    new_block = f"### {today_str}\n\n{new_ideas}\n\n"
    updated = new_block + (existing_section if existing_section else "")

    vault_path = f"{AUTO_IDEAS_SUBDIR}/{name}.md"
    return escribir_en_vault_sync(
        PERSONAL_VAULT_REPO, vault_path, updated,
        "💡 Pending Ideas", "actualizar", "automation-ideas"
    )


def main():
    if not GEMINI_API_KEY:
        log("[automation-ideas] ❌ GEMINI_API_KEY not found")
        sys.exit(1)

    projects = load_projects()
    if not projects:
        log("[automation-ideas] ❌ No projects found in config.json")
        sys.exit(1)

    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    log(f"[automation-ideas] {now.strftime('%Y-%m-%d %H:%M')} — {len(projects)} projects")

    git_pull(PERSONAL_VAULT, "personal-vault")

    notes = load_recent_notes(days=7)
    log(f"[automation-ideas] Daily notes loaded: {list(notes.keys())}")

    already_done = [
        slug for slug, name, _ in projects
        if section_exists_today(AUTO_IDEAS_DIR / f"{name}.md", today_str)
    ]

    if len(already_done) == len(projects):
        log(f"[automation-ideas] All files already have section {today_str} — skipping.")
        sys.exit(0)

    notes_block = ""
    for d, content in notes.items():
        notes_block += f"\n===DAILY {d}===\n{content}\n===END {d}===\n"
    if not notes_block:
        notes_block = "(No daily notes found in the last 7 days)"

    log("[automation-ideas] Generating ideas with Gemini...")
    gemini_output = generate_ideas(today_str, notes_block, projects)

    if not gemini_output:
        log("[automation-ideas] ❌ Gemini returned empty response")
        sys.exit(1)

    ideas_by_slug = parse_ideas(gemini_output, projects)
    log(f"[automation-ideas] Ideas generated for: {list(ideas_by_slug.keys())}")

    written = 0
    for slug, name, _ in projects:
        if slug in already_done:
            log(f"[automation-ideas] {name}: already has section {today_str} — skipping")
            continue
        if slug not in ideas_by_slug:
            log(f"[automation-ideas] ⚠️ {name}: Gemini did not generate ideas for this slug")
            continue
        file_path = AUTO_IDEAS_DIR / f"{name}.md"
        ok = insert_ideas_into_file(file_path, slug, name, today_str, ideas_by_slug[slug])
        if ok:
            log(f"[automation-ideas] ✅ {name}.md updated")
            written += 1
        else:
            log(f"[automation-ideas] ⚠️ {name}.md: vault_writer failed")

    log(f"[automation-ideas] ✅ Done — {written}/{len(projects)} files updated.")


if __name__ == "__main__":
    main()
