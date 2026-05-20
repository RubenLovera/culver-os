"""CRUD for daily, weekly and monthly Obsidian notes.

Config is read from the file at CONFIG_PATH env var (default: /culver-os/config.json).
Expected config sections:
  user.name, user.timezone
  personal_vault.daily_notes_dir, personal_vault.weekly_reviews_dir, personal_vault.monthly_reviews_dir
  daily_note.habits     — list of habit names (up to 5)
  daily_note.ventures   — list of venture/project names to create task sections for
  daily_note.verses     — true/false (optional, default false)
"""
import os
import re
import json
import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from functools import lru_cache
from pathlib import Path

from tools.obsidian import pull, write as obsidian_write, _vault_path, _git

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _config() -> dict:
    path = os.environ.get("CONFIG_PATH", "/culver-os/config.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load config from %s: %s", path, e)
        return {}


def _tz() -> ZoneInfo:
    return ZoneInfo(_config().get("user", {}).get("timezone", "America/Los_Angeles"))


def _daily_dir() -> str:
    return _config().get("personal_vault", {}).get("daily_notes_dir", "Daily Notes")


def _weekly_dir() -> str:
    return _config().get("personal_vault", {}).get("weekly_reviews_dir", "Weekly Reviews")


def _monthly_dir() -> str:
    return _config().get("personal_vault", {}).get("monthly_reviews_dir", "Monthly Reviews")


def _habits() -> list[str]:
    return _config().get("daily_note", {}).get("habits", ["Gym", "Meditation", "Finances"])


def _ventures() -> list[str]:
    return _config().get("daily_note", {}).get("ventures", [])


def _use_verses() -> bool:
    return _config().get("daily_note", {}).get("verses", False)


# ---------------------------------------------------------------------------
# Constants (exposed for imports)
# ---------------------------------------------------------------------------

DIAS  = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

_VERSES = [
    '"No temas, porque yo estoy contigo; no desmayes, porque yo soy tu Dios." — Isaías 41:10',
    '"Todo lo puedo en Cristo que me fortalece." — Filipenses 4:13',
    '"El Señor es mi pastor; nada me faltará." — Salmos 23:1',
    '"Encomienda al Señor tu camino; confía en él, y él actuará." — Salmos 37:5',
    '"Porque yo sé los planes que tengo para vosotros, planes de bienestar." — Jeremías 29:11',
    '"Pon en manos del Señor todas tus obras, y tus proyectos se cumplirán." — Proverbios 16:3',
    '"El Señor es mi luz y mi salvación; ¿a quién temeré?" — Salmos 27:1',
    '"Confía en el Señor con todo tu corazón." — Proverbios 3:5',
    '"Porque Dios no nos ha dado espíritu de cobardía, sino de poder." — 2 Timoteo 1:7',
    '"Buscad primero el reino de Dios y su justicia." — Mateo 6:33',
]

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def today_la() -> date:
    from datetime import datetime
    return datetime.now(_tz()).date()


def daily_path(d: date = None) -> str:
    d = d or today_la()
    return f"{_daily_dir()}/{d.isoformat()}.md"


def weekly_path(d: date = None) -> str:
    d = d or today_la()
    iso = d.isocalendar()
    return f"{_weekly_dir()}/W{iso[0]}-{iso[1]:02d}.md"


def monthly_path(d: date = None) -> str:
    d = d or today_la()
    return f"{_monthly_dir()}/{d.strftime('%Y-%m')}.md"


def get_verse(d: date = None) -> str:
    if not _use_verses():
        return ""
    d = d or today_la()
    return _VERSES[d.toordinal() % len(_VERSES)]


# ---------------------------------------------------------------------------
# Low-level note I/O
# ---------------------------------------------------------------------------

def note_exists(path: str) -> bool:
    return os.path.isfile(os.path.join(_vault_path("personal"), path))


def read_note(path: str) -> str | None:
    full = os.path.join(_vault_path("personal"), path)
    try:
        with open(full, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error("read_note %s: %s", path, e)
        return None


def _write_and_push(path: str, content: str, msg: str) -> bool:
    vault_path = _vault_path("personal")
    full_path = os.path.join(vault_path, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    _git(vault_path, "add", path)
    try:
        _git(vault_path, "commit", "-m", msg)
    except RuntimeError as e:
        if "nothing to commit" in str(e):
            return True
        raise
    for attempt in range(2):
        try:
            _git(vault_path, "push")
            return True
        except RuntimeError as e:
            logger.warning("push attempt %d: %s", attempt + 1, e)
    return False


# ---------------------------------------------------------------------------
# Template builder
# ---------------------------------------------------------------------------

def _habit_checkboxes() -> str:
    return "\n".join(f"- [ ] {h}" for h in _habits())


def _venture_sections() -> str:
    ventures = _ventures()
    if not ventures:
        return "### General\n- [ ] \n"
    return "\n\n".join(f"### {v}\n- [ ] " for v in ventures)


def build_daily_template(d: date) -> str:
    yesterday = (d - timedelta(days=1)).isoformat()
    tomorrow  = (d + timedelta(days=1)).isoformat()
    label     = f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"
    verse     = get_verse(d)
    verse_section = f"\n## Palabra del Día\n> {verse}\n" if verse else ""

    habits_md = _habit_checkboxes()
    ventures_md = _venture_sections()

    return f"""---
date: {d.isoformat()}
tags: daily-note
---

# {label}
← [[{yesterday}]] | [[{tomorrow}]] →

## Morning Check-in
- ¿Cómo amaneciste?
- Intención del día:
- Una cosa que no puedo dejar sin hacer:

## Resumen de Ayer
*(auto-llenado)*
{verse_section}
## Top 3 Prioridades del Día
1.
2.
3.

## Hábitos Diarios
{habits_md}

## Tareas por Área

{ventures_md}

## Finanzas del Día
- Gastos:
- Ingresos:

## Notas & Ideas


## Evening Review
- ¿Qué salió bien hoy?
- ¿Qué quedó pendiente?
- ¿Qué aprendí hoy?
- Hábitos completados: /5
- Energía del día (1-10):
- Una cosa que haría diferente mañana:
"""


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_today_note() -> tuple[bool, str]:
    """Create today's daily note if it doesn't exist. Returns (created, path)."""
    d = today_la()
    path = daily_path(d)
    if note_exists(path):
        return False, path
    pull("personal")
    content = build_daily_template(d)
    _write_and_push(path, content, f"daily-note: create {d.isoformat()}")
    return True, path


def get_yesterday_evening_summary() -> str:
    yesterday = today_la() - timedelta(days=1)
    content = read_note(daily_path(yesterday))
    if not content:
        return "Sin datos de ayer."
    m = re.search(r"## Evening Review\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        return "Sin datos de ayer."
    section = m.group(1)

    def extract(pattern):
        r = re.search(pattern, section)
        if not r:
            return ""
        val = r.group(1).strip().lstrip("-").strip()
        return val if val and val not in ("/5", "/10") else ""

    wins    = extract(r"¿Qué salió bien hoy\?\s*(.+)")
    habitos = extract(r"Hábitos completados:\s*(.+)")
    energia = extract(r"Energía del día \(1-10\):\s*(.+)")
    parts = []
    if wins:    parts.append(wins[:120])
    if habitos: parts.append(f"Hábitos: {habitos}")
    if energia: parts.append(f"Energía: {energia}/10")
    return " | ".join(parts) if parts else "Sin datos del evening review de ayer."


def fill_resumen_ayer(path: str) -> bool:
    vault_path = _vault_path("personal")
    full_path = os.path.join(vault_path, path)
    pull("personal")
    try:
        with open(full_path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return False
    resumen = get_yesterday_evening_summary()
    new_cont = re.sub(
        r"(## Resumen de Ayer\n)\*\(auto-llenado\)\*",
        rf"\g<1>{resumen}",
        content,
    )
    if new_cont == content:
        return False
    return _write_and_push(path, new_cont, "daily-note: auto-fill resumen ayer")


def update_fields(path: str, replacements: list[tuple[str, str]], commit_msg: str) -> bool:
    """Apply list of (search_pattern, replacement) regex subs then push."""
    vault_path = _vault_path("personal")
    full_path = os.path.join(vault_path, path)
    pull("personal")
    try:
        with open(full_path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return False
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content, count=1, flags=re.MULTILINE)
    return _write_and_push(path, content, commit_msg)


def append_to_section(path: str, section_header: str, lines: list[str], commit_msg: str) -> bool:
    """Append lines at the end of a markdown section."""
    vault_path = _vault_path("personal")
    full_path = os.path.join(vault_path, path)
    pull("personal")
    try:
        with open(full_path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return False
    escaped = re.escape(section_header)
    m = re.search(rf"{escaped}\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        return False
    insert_pos = m.end(0)
    addition = "\n" + "\n".join(lines)
    new_content = content[:insert_pos] + addition + content[insert_pos:]
    return _write_and_push(path, new_content, commit_msg)


def check_morning_filled(path: str) -> dict:
    content = read_note(path)
    if not content:
        return {}

    def has(pattern):
        m = re.search(pattern, content)
        return bool(m and m.group(1).strip())

    return {
        "how_woke_up": has(r"¿Cómo amaneciste\?\s*(.+)"),
        "intention":   has(r"Intención del día:\s*(.+)"),
        "one_thing":   has(r"Una cosa que no puedo dejar sin hacer:\s*(.+)"),
    }


def check_evening_filled(path: str) -> dict:
    content = read_note(path)
    if not content:
        return {k: False for k in ["wins", "pending", "learned", "habitos", "energia"]}

    def has(pattern):
        m = re.search(pattern, content, re.MULTILINE)
        if not m:
            return False
        val = m.group(1).strip()
        return bool(val) and val not in ("", "/5", "/10", "-")

    return {
        "wins":    has(r"¿Qué salió bien hoy\?\s*(.+)"),
        "pending": has(r"¿Qué quedó pendiente\?\s*(.+)"),
        "learned": has(r"¿Qué aprendí hoy\?\s*(.+)"),
        "habitos": has(r"Hábitos completados:\s*([^/\n]+\d)"),
        "energia": has(r"Energía del día \(1-10\):\s*(\d+)"),
    }


def aggregate_weekly_habits(week_start: date) -> dict:
    """Read 7 daily notes and return checked habit counts for the week."""
    habit_names = _habits()
    totals = {h: 0 for h in habit_names}
    for i in range(7):
        d = week_start + timedelta(days=i)
        content = read_note(daily_path(d))
        if not content:
            continue
        for h in habit_names:
            if re.search(rf"- \[x\].*{re.escape(h)}", content, re.I):
                totals[h] += 1
    return totals
