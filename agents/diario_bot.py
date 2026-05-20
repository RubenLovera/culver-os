#!/usr/bin/env python3
"""Diario Bot — Conversational note-owner agent for CulverOS.

Reads config from CONFIG_PATH env var (default: /culver-os/config.json).
Required env vars: TELEGRAM_TOKEN, GROUP_ID, DIARIO_THREAD_ID, GEMINI_API_KEY.
Optional env vars: PCP_AGENT_ID, PCP_TOKEN, PAPERCLIP_URL, PAPERCLIP_COMPANY_ID.
"""
import os
import json
import re
import logging
import asyncio
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from functools import lru_cache

from google import genai
from google.genai import types as genai_types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from tools.daily_note import (
    today_la, daily_path, weekly_path, monthly_path,
    create_today_note, fill_resumen_ayer, get_yesterday_evening_summary,
    check_morning_filled, check_evening_filled, aggregate_weekly_habits,
    read_note, note_exists, update_fields, append_to_section,
    build_daily_template, get_verse, DIAS, MESES,
)
from tools.voice import process_voice_note, summarize_extraction
from tools.obsidian import write, pull, _git
from tools.memory import (
    record_action,
    record_interaction,
    mark_acknowledged_by_message_id,
    extract_interaction,
    get_open_commitments,
)
from tools.paperclip import report_cost

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("diario_bot")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_ID       = int(os.environ["GROUP_ID"])
DIARIO_THREAD  = int(os.environ["DIARIO_THREAD_ID"])
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

_client = genai.Client(api_key=GEMINI_API_KEY)

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
        logger.warning("Could not load config: %s", e)
        return {}


def _tz() -> ZoneInfo:
    return ZoneInfo(_config().get("user", {}).get("timezone", "America/Los_Angeles"))


def _user_name() -> str:
    return _config().get("user", {}).get("name", "User")


def _ventures() -> list[str]:
    return _config().get("daily_note", {}).get("ventures", [])


def _habits() -> list[str]:
    return _config().get("daily_note", {}).get("habits", ["Gym", "Meditation", "Finances"])


STATE_FILE = os.environ.get("DIARIO_STATE_FILE", "/culver-os/diario_state.json")

# ---------------------------------------------------------------------------
# State — persisted daily, reset at midnight
# ---------------------------------------------------------------------------

DEFAULT_STATE = {
    "date": "",
    "morning_checkin": {"asked": False, "filled": False},
    "peso":            {"asked": False, "filled": False},
    "top3":            {"asked": False, "filled": False},
    "midday":          {"asked": False, "filled": False},
    "cierre":          {"asked": False, "filled": False},
    "evening":         {"asked": False, "filled": False},
    "conversation_history": [],
}


def load_state() -> dict:
    today = today_la().isoformat()
    if Path(STATE_FILE).exists():
        try:
            s = json.loads(Path(STATE_FILE).read_text())
            if s.get("date") == today:
                return s
        except Exception:
            pass
    state = {**DEFAULT_STATE, "date": today}
    save_state(state)
    return state


def save_state(state: dict):
    Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2))


def add_to_history(state: dict, role: str, content: str):
    history = state.setdefault("conversation_history", [])
    history.append({"role": role, "content": content, "ts": datetime.now(_tz()).isoformat()})
    state["conversation_history"] = history[-40:]


# ---------------------------------------------------------------------------
# Note status reader
# ---------------------------------------------------------------------------

def get_note_status(path: str) -> dict:
    if not note_exists(path):
        return {"exists": False, "summary": "Today's note doesn't exist yet."}

    content = read_note(path)

    def field_value(marker: str) -> str:
        for line in content.splitlines():
            if marker in line:
                after = line.split(marker, 1)[-1].strip().lstrip(":").strip()
                if after and after not in ("-", "—", "N/A"):
                    return after
        return ""

    def checkbox_count(habit_name: str) -> int:
        count = 0
        for line in content.splitlines():
            if "- [x]" in line.lower() and habit_name.lower() in line.lower():
                count += 1
        return count

    habits_status = {h: checkbox_count(h) > 0 for h in _habits()}

    status = {
        "exists": True,
        "morning_feeling":   field_value("¿Cómo amaneciste?"),
        "morning_intention": field_value("Intención del día"),
        "top3_filled":       bool(field_value("1.")),
        "habits":            habits_status,
        "evening": {
            "wins":       field_value("¿Qué salió bien hoy?"),
            "pendiente":  field_value("¿Qué quedó pendiente?"),
            "aprendizaje": field_value("¿Qué aprendí hoy?"),
            "habitos_5":  field_value("Hábitos completados"),
            "energia_10": field_value("Energía del día"),
        },
    }
    return status


# ---------------------------------------------------------------------------
# Gemini function declarations
# ---------------------------------------------------------------------------

def _build_tool_declarations() -> genai_types.Tool:
    ventures = _ventures()
    venture_enum = ventures if ventures else ["General"]

    return genai_types.Tool(function_declarations=[
        genai_types.FunctionDeclaration(
            name="save_field",
            description=(
                "Save a structured field to the daily note. "
                "Use when the user mentions: weight, calories, energy, habits completed, "
                "morning intention, how they woke up, or any morning check-in field."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": [
                            "morning_feeling", "morning_intention",
                            "energia_1_10", "habitos_completados",
                        ],
                        "description": "Field to save",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to save",
                    },
                },
                "required": ["field", "value"],
            },
        ),
        genai_types.FunctionDeclaration(
            name="save_task",
            description=(
                "Save a new or completed task to the correct area section. "
                "Use when the user mentions something they did, need to do, or completed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "enum": venture_enum,
                        "description": "Area or project the task belongs to",
                    },
                    "text": {
                        "type": "string",
                        "description": "Task description",
                    },
                    "completed": {
                        "type": "boolean",
                        "description": "True if the task is already done",
                    },
                },
                "required": ["area", "text", "completed"],
            },
        ),
        genai_types.FunctionDeclaration(
            name="save_idea",
            description=(
                "Save an idea, reflection, or free note to the Notes & Ideas section. "
                "Use when the user shares something that is neither a task nor structured data."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Idea or note text"},
                    "area": {"type": "string", "description": "Related area (optional)"},
                },
                "required": ["text"],
            },
        ),
        genai_types.FunctionDeclaration(
            name="save_finance",
            description=(
                "Save an expense or income to the Finances section. "
                "Use when the user mentions money, payments, expenses, income."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "type":        {"type": "string", "enum": ["expense", "income"]},
                    "amount":      {"type": "string", "description": "Amount with currency"},
                    "description": {"type": "string", "description": "Description"},
                },
                "required": ["type", "amount", "description"],
            },
        ),
        genai_types.FunctionDeclaration(
            name="save_evening_field",
            description=(
                "Save an evening review field. "
                "Use when the user answers end-of-day questions: wins, pending, learned, habits, energy."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": ["wins", "pending", "learned", "habitos_5", "energia_10"],
                    },
                    "value": {"type": "string"},
                },
                "required": ["field", "value"],
            },
        ),
        genai_types.FunctionDeclaration(
            name="save_top3",
            description="Save the top 3 priorities for the day.",
            parameters={
                "type": "object",
                "properties": {
                    "priority_1": {"type": "string"},
                    "priority_2": {"type": "string"},
                    "priority_3": {"type": "string"},
                },
                "required": ["priority_1"],
            },
        ),
    ])


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

FIELD_MAP = {
    "morning_feeling":    ("- ¿Cómo amaneciste?", "- ¿Cómo amaneciste? {value}"),
    "morning_intention":  ("- Intención del día:", "- Intención del día: {value}"),
    "energia_1_10":       ("- Energía del día (1-10):", "- Energía del día (1-10): {value}/10"),
    "habitos_completados":("- Hábitos completados: /5", "- Hábitos completados: {value}/5"),
}

EVENING_FIELD_MAP = {
    "wins":      ("- ¿Qué salió bien hoy?", "- ¿Qué salió bien hoy? {value}"),
    "pending":   ("- ¿Qué quedó pendiente?", "- ¿Qué quedó pendiente? {value}"),
    "learned":   ("- ¿Qué aprendí hoy?", "- ¿Qué aprendí hoy? {value}"),
    "habitos_5": ("- Hábitos completados: /5", "- Hábitos completados: {value}/5"),
    "energia_10":("- Energía del día (1-10):", "- Energía del día (1-10): {value}/10"),
}


def _area_section(area: str) -> str:
    return f"### {area}"


def execute_tool(name: str, args: dict, note_path: str) -> str:
    try:
        if name == "save_field":
            field = args["field"]
            value = str(args["value"])
            if field in FIELD_MAP:
                old, tpl = FIELD_MAP[field]
                update_fields(note_path, [(re.escape(old), tpl.format(value=value))], f"diario: {field}")
                result = f"saved {field}={value}"
                record_action(action_type="note_written", source_bot="diario", content=result, outcome="acknowledged")
                return result
            return f"field {field} not mapped"

        elif name == "save_task":
            area = args.get("area", "General")
            text = args["text"]
            completed = args.get("completed", False)
            checkbox = "- [x]" if completed else "- [ ]"
            section = _area_section(area)
            append_to_section(note_path, section, [f"{checkbox} {text}"], f"diario: task {area}")
            result = f"task in {area}: {text[:40]}"
            record_action(action_type="note_written", source_bot="diario", content=result, outcome="acknowledged")
            return result

        elif name == "save_idea":
            text = args["text"]
            area = args.get("area", "")
            note = f"- {text}" + (f" [{area}]" if area else "")
            append_to_section(note_path, "## Notas & Ideas", [note], "diario: idea")
            result = f"idea saved: {text[:40]}"
            record_action(action_type="note_written", source_bot="diario", content=result, outcome="acknowledged")
            return result

        elif name == "save_finance":
            ftype = args["type"]
            amount = args["amount"]
            desc = args["description"]
            emoji = "💸" if ftype == "expense" else "💰"
            line = f"- {emoji} **{ftype.capitalize()}:** {amount} — {desc}"
            append_to_section(note_path, "## Finanzas del Día", [line], f"diario: {ftype}")
            result = f"{ftype} saved: {amount}"
            record_action(action_type="note_written", source_bot="diario", content=result, outcome="acknowledged")
            return result

        elif name == "save_evening_field":
            field = args["field"]
            value = str(args["value"])
            if field in EVENING_FIELD_MAP:
                old, tpl = EVENING_FIELD_MAP[field]
                update_fields(note_path, [(re.escape(old), tpl.format(value=value))], f"diario: evening {field}")
                result = f"evening {field}={value}"
                record_action(action_type="note_written", source_bot="diario", content=result, outcome="acknowledged")
                return result
            return f"evening field {field} not mapped"

        elif name == "save_top3":
            p1 = args.get("priority_1", "")
            p2 = args.get("priority_2", "")
            p3 = args.get("priority_3", "")
            lines = []
            if p1: lines.append(f"1. {p1}")
            if p2: lines.append(f"2. {p2}")
            if p3: lines.append(f"3. {p3}")
            update_fields(note_path, [("1.\n2.\n3.", "\n".join(lines))], "diario: top3")
            result = f"top3 saved: {p1[:30]}"
            record_action(action_type="note_written", source_bot="diario", content=result, outcome="acknowledged")
            return result

        return f"tool {name} not recognized"

    except Exception as e:
        logger.error("execute_tool %s error: %s", name, e)
        return f"error in {name}: {e}"


# ---------------------------------------------------------------------------
# Core conversational agent
# ---------------------------------------------------------------------------

def _build_system_prompt(note_status: dict) -> str:
    now = datetime.now(_tz())
    time_str = now.strftime("%H:%M")
    date_str = today_la().strftime("%A %d de %B de %Y")
    user_name = _user_name()
    ventures_list = "\n".join(f"- {v}" for v in _ventures()) or "- (none configured)"

    return f"""You are Diario, the personal notes agent for {user_name}.

Your job: listen to what {user_name} says and help them capture their day — tasks, ideas, wins, habits, finances — into their Obsidian daily note.

Today is {date_str}. Current time: {time_str}.
Active projects:
{ventures_list}

Today's note status:
{json.dumps(note_status, ensure_ascii=False, indent=2)}

Behavior rules:
1. Listen to what {user_name} says and process the information
2. Use available tools to save data before responding
3. Respond in the user's language, direct and friendly, max 3 lines
4. Briefly confirm what you saved if you saved something
5. Ask at most 1 follow-up question if it makes sense
6. Do NOT ask about fields that are already filled (check note status above)
7. If the message is just a greeting or conversation with nothing to save, respond naturally without forcing note questions
8. You can reason about what they share — suggest ideas, spot opportunities, connect information"""


async def gemini_conversation_agent(user_message: str, history: list, note_path: str) -> str:
    note_status = get_note_status(note_path)
    system_prompt = _build_system_prompt(note_status)

    contents = []
    for msg in history[-20:]:
        role = msg["role"]
        text = msg["content"]
        if role in ("user", "model"):
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    diario_tools = _build_tool_declarations()

    for attempt in range(3):
        try:
            response = await asyncio.to_thread(
                _client.models.generate_content,
                model="gemini-2.5-flash",
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[diario_tools],
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 15 * (2 ** attempt)
                logger.warning("Gemini 429, retrying in %ds (attempt %d/3)", wait, attempt + 1)
                await asyncio.sleep(wait)
            else:
                raise

    try:
        pull("personal")
    except Exception as e:
        logger.warning("pull before tool execution failed: %s", e)

    response_text = ""
    tool_results = []

    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            response_text += part.text
        if hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            result = execute_tool(fc.name, dict(fc.args), note_path)
            tool_results.append(result)
            logger.info("Tool executed: %s → %s", fc.name, result)

    if not response_text.strip() and tool_results:
        response_text = "✅ " + " / ".join(tool_results[:3])

    return response_text.strip() or "📝 Received."


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

_app: Application = None


async def send(text: str):
    await _app.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=DIARIO_THREAD,
        text=text,
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

async def morning_kickoff():
    """5:45 AM — create note, fill yesterday summary, send morning greeting."""
    state = load_state()
    if state["morning_checkin"]["asked"]:
        return

    try:
        pull("personal")
    except Exception as e:
        logger.warning("morning pull failed: %s", e)

    created, path = create_today_note()
    if created:
        logger.info("Created daily note: %s", path)

    fill_resumen_ayer(path)
    verse = get_verse()

    commitments_block = ""
    try:
        commitments = get_open_commitments(n=3)
        if commitments:
            lines = [f"• {c['document']}" for c in commitments]
            commitments_block = "\n\n*Pending commitments:*\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("get_open_commitments failed: %s", e)

    verse_line = f"\n_{verse}_" if verse else ""
    greeting = (
        f"☀️ Good morning, {_user_name()}."
        f"{verse_line}"
        f"{commitments_block}\n\n"
        f"How did you wake up today? What's your intention for the day?"
    )
    await send(greeting)
    state["morning_checkin"]["asked"] = True
    add_to_history(state, "model", greeting)
    save_state(state)


async def _scheduled_checkin(hour_label: str, question: str, state_key: str):
    state = load_state()
    if state[state_key]["asked"] or state[state_key]["filled"]:
        return

    note_path = daily_path()
    note_status = get_note_status(note_path)
    history = state.get("conversation_history", [])

    check_prompt = (
        f"It's {hour_label}. I need to know if '{question}' was already covered in today's conversation. "
        f"Note status: {json.dumps(note_status, ensure_ascii=False)}. "
        f"If the field is already filled or was mentioned in the conversation, respond only: SKIP. "
        f"If not covered, ask the question naturally in 1 sentence."
    )

    try:
        gemini_history = [
            {"role": m["role"], "parts": [{"text": m["content"]}]}
            for m in history[-10:]
            if m.get("role") in ("user", "model")
        ]
        resp = await asyncio.to_thread(
            _client.models.generate_content,
            model="gemini-2.5-flash",
            contents=gemini_history + [{"role": "user", "parts": [{"text": check_prompt}]}],
            config=genai_types.GenerateContentConfig(
                system_instruction=_build_system_prompt(note_status),
            ),
        )
        msg = resp.text.strip()
        if msg.upper().startswith("SKIP"):
            logger.info("Scheduled checkin %s skipped — already covered", state_key)
            state[state_key]["asked"] = True
            save_state(state)
            return
        await send(msg)
        add_to_history(state, "model", msg)
        state[state_key]["asked"] = True
        save_state(state)
    except Exception as e:
        logger.error("_scheduled_checkin error: %s", e)
        await send(question)


async def followup_peso():
    """8:00 AM — weight/calories check-in."""
    await _scheduled_checkin("8 AM", "Did you weigh yourself today? How are calories looking?", "peso")


async def followup_top3():
    """11:00 AM — top 3 priorities."""
    await _scheduled_checkin("11 AM", "What are your top 3 priorities for today?", "top3")


async def followup_midday():
    """2:00 PM — midday capture."""
    await _scheduled_checkin("2 PM", "How's the day going? Anything completed or to capture?", "midday")


async def followup_cierre():
    """5:00 PM — pre-close check-in."""
    await _scheduled_checkin("5 PM", "Before wrapping up: anything you want to log before end of work?", "cierre")


async def evening_review():
    """9:00 PM — smart evening review using conversation history."""
    state = load_state()
    if state["evening"]["asked"]:
        return

    try:
        pull("personal")
    except Exception:
        pass

    note_path = daily_path()
    note_status = get_note_status(note_path)
    history = state.get("conversation_history", [])

    evening_prompt = (
        "It's 9 PM — time for the Evening Review. "
        "Look at the note status and today's conversation history. "
        "Ask only about fields that are empty AND were NOT mentioned today. "
        "If multiple fields are empty, ask them all naturally (not as a rigid list). "
        "If everything is filled, say a brief closing. Max 5 lines."
    )

    try:
        gemini_history = [
            {"role": m["role"], "parts": [{"text": m["content"]}]}
            for m in history[-16:]
            if m.get("role") in ("user", "model")
        ]
        resp = await asyncio.to_thread(
            _client.models.generate_content,
            model="gemini-2.5-flash",
            contents=gemini_history + [{"role": "user", "parts": [{"text": evening_prompt}]}],
            config=genai_types.GenerateContentConfig(
                system_instruction=_build_system_prompt(note_status),
            ),
        )
        msg = "🌙 *Evening Review*\n\n" + resp.text.strip()
        await send(msg)
        add_to_history(state, "model", msg)
        state["evening"]["asked"] = True
        save_state(state)
    except Exception as e:
        logger.error("evening_review error: %s", e)
        await send("🌙 How did the day close? What went well, what's pending, and what did you learn?")


async def evening_reminder():
    """10:30 PM — re-ask only if critical evening fields still empty."""
    state = load_state()
    if not state["evening"]["asked"] or state["evening"]["filled"]:
        return

    try:
        pull("personal")
    except Exception:
        pass

    note_path = daily_path()
    note_status = get_note_status(note_path)
    ev = note_status.get("evening", {})

    critical_missing = []
    if not ev.get("wins"):       critical_missing.append("what went well")
    if not ev.get("habitos_5"):  critical_missing.append("habits (/5)")
    if not ev.get("energia_10"): critical_missing.append("energy (1-10)")

    if len(critical_missing) >= 2:
        msg = f"🔔 Before sleep: {' / '.join(critical_missing)}"
        await send(msg)
        add_to_history(state, "model", msg)
        save_state(state)


async def weekly_note_job():
    """Sunday 8:00 PM — create weekly note with habit aggregation."""
    today = today_la()
    if today.weekday() != 6:
        return

    try:
        from isoweek import Week
    except ImportError:
        logger.error("isoweek not installed — pip install isoweek")
        return

    try:
        pull("personal")
    except Exception:
        pass

    w = Week.withdate(today)
    week_start = w.monday()
    habits = aggregate_weekly_habits(week_start)
    habit_names = list(habits.keys())

    path = weekly_path(today)
    if note_exists(path):
        state = load_state()
        msg = "📊 Weekly note already exists. What's your intention for this week and your top 5?"
        await send(msg)
        add_to_history(state, "model", msg)
        save_state(state)
        return

    year = today.year
    week_num = today.isocalendar()[1]
    import datetime as dt_module
    week_end = week_start + dt_module.timedelta(days=6)

    def fmt(d): return f"{d.day} {MESES[d.month-1]}"

    habit_rows = "\n".join(
        f"| {h} | | {habits[h]} | | | | | | |"
        for h in habit_names
    )

    ventures = _config().get("daily_note", {}).get("ventures", [])
    venture_sections = "\n\n".join(
        f"### {v}\n- **Objective:**\n- **Top 3:**\n  1.\n  2.\n  3."
        for v in ventures
    ) or "### General\n- **Objective:**"

    content = f"""---
date: {week_start.isoformat()}
week_number: {week_num}
year: {year}
tags: [weekly-planning, planning]
---

# Week {week_num} of {year}
**{fmt(week_start)} – {fmt(week_end)} {year}**

← [[W{year}-{(week_num-1):02d}]] | [[W{year}-{(week_num+1):02d}]] →

## Intention of the week


## Plan by Project

{venture_sections}

## Top 5 tasks of the week
1.
2.
3.
4.
5.

## Finances
- Expected income:
- Expected expenses:
- Savings goal:

## Habits & Health
| Habit | Mon | Tue | Wed | Thu | Fri | Sat | Sun | Total |
|-------|-----|-----|-----|-----|-----|-----|-----|-------|
{habit_rows}

## Closing last week

### What went well?

### Key lessons

### What didn't I finish? Why?
"""
    ok = write(path, content, f"diario: weekly note W{year}-{week_num:02d}", vault="personal")
    state = load_state()
    habits_summary = ", ".join(f"{h}: {v}/7" for h, v in habits.items())
    msg = (
        f"📊 *Weekly Note W{year}-{week_num:02d}* created.\n"
        f"Last week's habits — {habits_summary}\n\n"
        f"What's your intention for this week and your top 5?"
    ) if ok else "⚠️ Could not create weekly note. Check logs."
    await send(msg)
    add_to_history(state, "model", msg)
    save_state(state)


async def monthly_note_job():
    """1st of month 9:00 AM — create monthly note."""
    today = today_la()
    if today.day != 1:
        return

    try:
        pull("personal")
    except Exception:
        pass

    month_name = MESES[today.month - 1].capitalize()
    path = f"{_config().get('personal_vault', {}).get('monthly_reviews_dir', 'Monthly Reviews')}/{today.year}-{today.month:02d}.md"

    if note_exists(path):
        await send(f"📅 Monthly note for {month_name} already exists.")
        return

    ventures = _config().get("daily_note", {}).get("ventures", [])
    venture_sections = "\n".join(f"### {v}" for v in ventures) or "### General"

    content = f"""---
date: {today.isoformat()}
month: {today.month}
year: {today.year}
tags: [monthly-review]
---

# {month_name} {today.year}

## Intention of the month


## Top 3 wins from last month
1.
2.
3.

## Objectives this month
{venture_sections}

## Finances
- Savings goal:
- Projected income:

## Habits
"""
    ok = write(path, content, f"diario: monthly note {today.year}-{today.month:02d}", vault="personal")
    state = load_state()
    msg = (
        f"📅 *Monthly Note {month_name} {today.year}* created.\n"
        f"What were your top 3 wins last month and what's your intention for {month_name}?"
    ) if ok else "⚠️ Could not create monthly note."
    await send(msg)
    add_to_history(state, "model", msg)
    save_state(state)


async def reset_daily_state():
    """Midnight — reset state for new day."""
    state = {**DEFAULT_STATE, "date": today_la().isoformat()}
    save_state(state)
    logger.info("Daily state reset for %s", state["date"])


# ---------------------------------------------------------------------------
# CulverBrain v3.0 — Capa 5 + 6 hooks
# ---------------------------------------------------------------------------

async def _extract_and_record(user_message: str, bot_response: str):
    try:
        interaction = extract_interaction(user_message, bot_response, source_bot="diario")
        if interaction:
            record_interaction(**interaction, source_bot="diario")
    except Exception as e:
        logger.warning("_extract_and_record failed: %s", e)


async def post_message_hook(user_message: str, bot_response: str, sent_message):
    try:
        record_action(
            action_type="message_sent",
            source_bot="diario",
            content=bot_response[:200],
            outcome="pending",
            message_id=sent_message.message_id,
        )
    except Exception as e:
        logger.warning("record_action failed: %s", e)
    asyncio.create_task(_extract_and_record(user_message, bot_response))


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    thread_id = getattr(msg, "message_thread_id", None)
    if msg.chat_id != GROUP_ID or thread_id != DIARIO_THREAD:
        return

    state = load_state()

    if msg.reply_to_message:
        try:
            mark_acknowledged_by_message_id(msg.reply_to_message.message_id)
        except Exception as e:
            logger.warning("mark_acknowledged failed: %s", e)

    if msg.voice or msg.audio:
        await handle_voice(msg, state)
        return

    text = (msg.text or "").strip()
    if not text:
        return

    note_path = daily_path()
    history = state.get("conversation_history", [])
    add_to_history(state, "user", text)
    save_state(state)

    try:
        response = await gemini_conversation_agent(text, history, note_path)
    except Exception as e:
        logger.error("gemini_conversation_agent error: %s", e)
        response = "❌ Had trouble processing your message. Please try again."

    sent_message = await _app.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=DIARIO_THREAD,
        text=response,
        parse_mode="Markdown",
    )
    asyncio.create_task(post_message_hook(text, response, sent_message))
    add_to_history(state, "model", response)
    save_state(state)


async def handle_voice(msg, state: dict):
    try:
        file_obj = msg.voice or msg.audio
        file = await _app.bot.get_file(file_obj.file_id)
        audio_bytes = await file.download_as_bytearray()

        await send("🎙️ Processing audio...")

        result = await process_voice_note(bytes(audio_bytes), "audio/ogg")
        summary = summarize_extraction(result)

        if not result.get("ok"):
            await send(f"{summary}\nSend it again or write it out.")
            return

        note_path = daily_path()
        try:
            pull("personal")
        except Exception:
            pass

        transcription = result.get("transcription", "")
        if transcription:
            add_to_history(state, "user", f"[Audio transcribed]: {transcription}")
            history = state.get("conversation_history", [])
            response = await gemini_conversation_agent(
                f"[Audio]: {transcription}", history, note_path
            )
            await send(response)
            add_to_history(state, "model", response)
            save_state(state)
        else:
            await send(summary)

    except Exception as e:
        logger.error("handle_voice error: %s", e)
        await send("❌ Could not process audio. Send it again or write it out.")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

def main():
    global _app

    tz = _tz()

    _app = Application.builder().token(TELEGRAM_TOKEN).build()
    _app.add_handler(MessageHandler(filters.ALL, handle_message))

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(morning_kickoff,   "cron", hour=5,  minute=45)
    scheduler.add_job(followup_peso,     "cron", hour=8,  minute=0)
    scheduler.add_job(followup_top3,     "cron", hour=11, minute=0)
    scheduler.add_job(followup_midday,   "cron", hour=14, minute=0)
    scheduler.add_job(followup_cierre,   "cron", hour=17, minute=0)
    scheduler.add_job(evening_review,    "cron", hour=21, minute=0)
    scheduler.add_job(evening_reminder,  "cron", hour=22, minute=30)
    scheduler.add_job(weekly_note_job,   "cron", day_of_week="sun", hour=20, minute=0)
    scheduler.add_job(monthly_note_job,  "cron", day=1, hour=9, minute=0)
    scheduler.add_job(reset_daily_state, "cron", hour=0, minute=0)

    async def post_init(app):
        scheduler.start()
        logger.info("Diario Bot started. Scheduler running.")

    _app.post_init = post_init
    _app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
