"""
Admin Bot — Agente administrador del Personal AI OS.
Nombre elegido por el usuario en el onboarding (AGENT_NAME).
Corre 24/7 en VPS via systemd. Accede a las 6 capas del CulverBrain.
"""

import asyncio
import glob
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.getenv("CULVER_OS_DIR", "/root/culver-os"))

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google import genai

from tools.brain import query as brain_query
from tools.memory import (
    extract_interaction,
    get_open_commitments,
    mark_acknowledged_by_message_id,
    query_actions,
    query_interactions,
    record_action,
    record_interaction,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config (inyectada via .env por generate_env.py) ──────────────────────────

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
GROUP_ID         = int(os.environ["GROUP_ID"])
ADMIN_THREAD_ID  = int(os.environ["ADMIN_THREAD_ID"])
GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
AGENT_NAME       = os.environ["AGENT_NAME"]
BRAIN_NAME       = os.environ["BRAIN_NAME"]
CULVER_OS_DIR    = os.getenv("CULVER_OS_DIR", "/root/culver-os")
MODEL            = "gemini-2.5-flash"

DAILY_NOTES_DIR   = os.path.join(CULVER_OS_DIR, "vaults", "obsidian-vault", os.getenv("DAILY_NOTES_SUBDIR", "Daily Notes"))
WEEKLY_REVIEWS_DIR = os.path.join(CULVER_OS_DIR, "vaults", "obsidian-vault", os.getenv("WEEKLY_REVIEWS_SUBDIR", "Weekly Reviews"))
MAX_HISTORY_TURNS = 20

_client = genai.Client(api_key=GEMINI_API_KEY)

# ── Keywords para routing de capas ────────────────────────────────────────────

TEMPORAL_KEYWORDS = [
    "recent", "last week", "today", "yesterday", "this week",
    "reciente", "últimos", "esta semana", "hoy", "ayer",
    "qué pasó", "cómo estuvo", "resumen", "summary",
]

ACTION_KEYWORDS = [
    "what did you do", "what happened", "did the script run",
    "qué hiciste", "qué corrió", "qué mandaste", "acciones",
    "resultado", "briefing", "executed",
]

# ── System prompt ─────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    parts = []
    for path in [
        os.path.join(CULVER_OS_DIR, "identity.md"),
        os.path.join(CULVER_OS_DIR, "user.md"),
    ]:
        try:
            with open(path) as f:
                parts.append(f.read())
        except FileNotFoundError:
            logger.warning(f"Context file not found: {path}")
    parts.append(
        f"\nYou are {AGENT_NAME}, the admin agent of this Personal AI OS. "
        f"You are running as a Telegram bot on the user's VPS. "
        f"You have access to the brain ({BRAIN_NAME}) and all 6 memory layers. "
        f"Be direct, helpful, and use the context injected below each message."
    )
    return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT = load_system_prompt()

_histories: dict = {}


def get_history(user_id: int) -> list:
    return _histories.setdefault(user_id, [])


def trim_history(user_id: int):
    h = _histories.get(user_id, [])
    if len(h) > MAX_HISTORY_TURNS * 2:
        _histories[user_id] = h[-(MAX_HISTORY_TURNS * 2):]


# ── Context builders (6 capas) ────────────────────────────────────────────────

def is_temporal_query(text: str) -> bool:
    return any(kw in text.lower() for kw in TEMPORAL_KEYWORDS)


def is_action_query(text: str) -> bool:
    return any(kw in text.lower() for kw in ACTION_KEYWORDS)


def get_recent_notes_context(days: int = 7) -> str:
    """Capa 3b — Daily notes recientes desde filesystem."""
    try:
        today = datetime.now().date()
        parts = ["[Recent daily notes:]"]
        found = 0
        for i in range(days):
            date = today - timedelta(days=i)
            path = os.path.join(DAILY_NOTES_DIR, f"{date}.md")
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()
                if len(content.strip()) > 50:
                    parts.append(f"\n### {date}\n{content[:1200]}")
                    found += 1
        if found == 0:
            return ""
        weekly_files = sorted(glob.glob(os.path.join(WEEKLY_REVIEWS_DIR, "W*.md")))
        if weekly_files:
            with open(weekly_files[-1]) as f:
                weekly_content = f.read()
            if len(weekly_content.strip()) > 50:
                week_name = os.path.basename(weekly_files[-1]).replace(".md", "")
                parts.append(f"\n### Weekly Review {week_name}\n{weekly_content[:800]}")
        return "\n".join(parts)
    except Exception as e:
        logger.warning(f"get_recent_notes_context failed: {e}")
        return ""


def get_brain_context(text: str) -> str:
    """Capa 3 — ChromaDB {brain_name}_brain."""
    try:
        results = brain_query(text, top_n=5)
        if not results or not results.get("documents") or not results["documents"][0]:
            return ""
        relevant = [
            (doc, dist, meta)
            for doc, dist, meta in zip(
                results["documents"][0],
                results["distances"][0],
                results["metadatas"][0],
            )
            if dist < 0.7
        ]
        if not relevant:
            return ""
        parts = ["[Vault context — relevant results:]"]
        for doc, dist, meta in relevant[:3]:
            venture = meta.get("venture", meta.get("source", ""))
            label = f"[{venture}] (score: {1 - dist:.2f})" if venture else f"(score: {1 - dist:.2f})"
            parts.append(f"\n{label}:\n{doc[:600]}")
        return "\n".join(parts)
    except Exception as e:
        logger.warning(f"Brain query failed: {e}")
        return ""


def get_interactions_context(text: str) -> str:
    """Capa 5 — decisiones y compromisos relevantes al query."""
    try:
        interactions = query_interactions(text, n=5)
        if not interactions:
            return ""
        lines = ["[Relevant decisions and commitments:]"]
        for item in interactions:
            itype = item.get("interaction_type", "?")
            content = item.get("document", "")
            date = item.get("date", "")
            lines.append(f"[{itype}] {content} ({date})")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Interactions query failed: {e}")
        return ""


def get_commitments_context() -> str:
    """Capa 5 — compromisos abiertos, siempre incluidos proactivamente."""
    try:
        commitments = get_open_commitments(n=3)
        if not commitments:
            return ""
        lines = ["[Open commitments:]"]
        for item in commitments:
            content = item.get("document", "")
            date = item.get("date", "")
            lines.append(f"- {content} (since {date})")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"get_open_commitments failed: {e}")
        return ""


def get_actions_context(text: str) -> str:
    """Capa 6 — acciones recientes, solo si es action query."""
    try:
        actions = query_actions(text, n=5)
        if not actions:
            return ""
        lines = ["[Recent system actions:]"]
        for item in actions:
            atype = item.get("action_type", "?")
            content = item.get("document", "")
            bot = item.get("source_bot", "")
            outcome = item.get("outcome", "?")
            date = item.get("date", "")
            lines.append(f"[{atype}] {content} ({bot}, outcome:{outcome}, {date})")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Actions query failed: {e}")
        return ""


# ── Post-message hooks ────────────────────────────────────────────────────────

async def _extract_and_record(user_message: str, bot_response: str):
    """Extrae y persiste interaction en Capa 5. Corre en background."""
    try:
        interaction = extract_interaction(user_message, bot_response, source_bot="admin")
        if interaction:
            record_interaction(**interaction, source_bot="admin")
    except Exception as e:
        logger.warning(f"_extract_and_record failed: {e}")


async def post_message_hook(user_message: str, bot_response: str, sent_message):
    """Dispara después de cada respuesta. No bloquea el handler."""
    try:
        record_action(
            action_type="message_sent",
            source_bot="admin",
            content=bot_response[:200],
            outcome="pending",
            message_id=sent_message.message_id,
        )
    except Exception as e:
        logger.warning(f"record_action failed: {e}")
    asyncio.create_task(_extract_and_record(user_message, bot_response))


# ── Telegram handler ──────────────────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat_id != GROUP_ID:
        return
    if update.message.message_thread_id != ADMIN_THREAD_ID:
        return

    text = update.message.text or ""
    if not text.strip():
        return

    if update.message.reply_to_message:
        try:
            mark_acknowledged_by_message_id(update.message.reply_to_message.message_id)
        except Exception as e:
            logger.warning(f"mark_acknowledged_by_message_id failed: {e}")

    ctx_parts = []

    if is_temporal_query(text):
        ctx = get_recent_notes_context(days=7)
        if ctx:
            ctx_parts.append(ctx)

    brain_ctx = get_brain_context(text)
    if brain_ctx:
        ctx_parts.append(brain_ctx)

    interactions_ctx = get_interactions_context(text)
    if interactions_ctx:
        ctx_parts.append(interactions_ctx)

    commitments_ctx = get_commitments_context()
    if commitments_ctx:
        ctx_parts.append(commitments_ctx)

    if is_action_query(text):
        actions_ctx = get_actions_context(text)
        if actions_ctx:
            ctx_parts.append(actions_ctx)

    if ctx_parts:
        augmented = "\n\n".join(ctx_parts) + f"\n\n---\n\nUser message: {text}"
    else:
        augmented = text

    user_id = update.message.from_user.id
    history = get_history(user_id)
    history.append({"role": "user", "parts": [{"text": augmented}]})
    trim_history(user_id)

    reply = None
    for attempt in range(3):
        try:
            resp = await asyncio.to_thread(
                _client.models.generate_content,
                model=MODEL,
                contents=history,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            reply = resp.text
            history.append({"role": "model", "parts": [{"text": reply}]})
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 15 * (2 ** attempt)
                logger.warning(f"Gemini 429, retrying in {wait}s (attempt {attempt + 1}/3)")
                await asyncio.sleep(wait)
            else:
                logger.error(f"LLM call failed: {e}")
                history.pop()
                reply = "Error processing your message — please try again in a moment."
                break

    sent_message = await update.message.reply_text(reply)
    asyncio.create_task(post_message_hook(text, reply, sent_message))


# ── Morning kickoff ───────────────────────────────────────────────────────────

async def morning_kickoff(app):
    """Heartbeat matutino: compromisos pendientes + estado del sistema."""
    try:
        commitments = get_open_commitments(n=5)
        if commitments:
            lines = [f"☀️ Good morning. Open commitments:"]
            for c in commitments:
                lines.append(f"- {c.get('document', '')} (since {c.get('date', '')})")
            msg = "\n".join(lines)
        else:
            msg = f"☀️ Good morning. No open commitments. System running normally."
        await app.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=ADMIN_THREAD_ID,
            text=msg,
        )
        record_action("briefing_sent", "admin", msg[:200], outcome="pending")
    except Exception as e:
        logger.error(f"morning_kickoff failed: {e}")


async def post_init(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(morning_kickoff, "cron", hour=6, minute=30, args=[app])
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info(f"{AGENT_NAME} bot ready — brain: {BRAIN_NAME} — listening on thread {ADMIN_THREAD_ID}")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
