#!/usr/bin/env python3
"""
log_watcher.py — Real-time log monitor for CulverOS bots.
Watches bot systemd services via journalctl for ERROR lines.
Sends Telegram alerts to the admin topic with 5-min cooldown per source.

Env vars (from .env.admin):
  TELEGRAM_TOKEN    — admin bot token
  GROUP_ID          — Telegram group ID
  ADMIN_THREAD_ID   — thread ID for admin alerts
  MONITOR_SERVICES  — comma-separated list of systemd services to watch
                      (default: "admin-bot,diario-bot")
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Bot

load_dotenv(".env.admin")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_ID       = int(os.environ["GROUP_ID"])
ADMIN_THREAD   = int(os.environ["ADMIN_THREAD_ID"])
TZ             = ZoneInfo(os.environ.get("USER_TIMEZONE", "America/Los_Angeles"))

_raw_services = os.environ.get("MONITOR_SERVICES", "admin-bot,diario-bot")
BOT_SERVICES  = [s.strip() for s in _raw_services.split(",") if s.strip()]

ERROR_KEYWORDS  = ["[ERROR]", "ERROR:", "Traceback (most recent", "CRITICAL", "Failed with result"]
IGNORE_KEYWORDS = ["getUpdates", "log_watcher"]
COOLDOWN        = timedelta(minutes=5)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("log_watcher")

_last_alert: dict[str, datetime] = {}

SOURCES = [
    {
        "name": svc,
        "cmd": ["journalctl", "-u", svc, "-f", "-n", "0", "--output=cat"],
    }
    for svc in BOT_SERVICES
]


def is_error(line: str) -> bool:
    if any(kw in line for kw in IGNORE_KEYWORDS):
        return False
    return any(kw in line for kw in ERROR_KEYWORDS)


async def send_alert(bot: Bot, source: str, line: str):
    now  = datetime.now(TZ)
    last = _last_alert.get(source)
    if last and (now - last) < COOLDOWN:
        return

    _last_alert[source] = now
    time_str = now.strftime("%H:%M:%S")
    short = line.strip()[:280]
    text  = f"🔴 *[{source}]* ERROR\n`{short}`\n_{time_str}_"

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=ADMIN_THREAD,
            text=text,
            parse_mode="Markdown",
        )
        logger.info("Alert sent for %s", source)
    except Exception as e:
        logger.error("Failed to send alert: %s", e)


async def watch(bot: Bot, source: dict):
    name = source["name"]
    cmd  = source["cmd"]
    logger.info("Watching %s", name)

    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            async for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace")
                if is_error(line):
                    logger.info("Error in %s: %s", name, line.strip()[:120])
                    await send_alert(bot, name, line)
        except Exception as e:
            logger.error("Watcher %s crashed: %s — restarting in 5s", name, e)

        await asyncio.sleep(5)


async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    now = datetime.now(TZ).strftime("%H:%M")
    services_str = ", ".join(BOT_SERVICES)

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=ADMIN_THREAD,
            text=f"👁 *Log Watcher* online — monitoring: {services_str} ({now})",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("Startup message failed: %s", e)

    await asyncio.gather(*(watch(bot, s) for s in SOURCES))


if __name__ == "__main__":
    asyncio.run(main())
