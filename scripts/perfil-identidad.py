"""
perfil-identidad.py — Regenerates index/perfil-identidad.md in the agent vault.

Synthesizes the user's current identity, goals, and context from recent notes.
Runs Sundays at 15:50 UTC.
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


def main():
    config = load_config()
    user_name = config.get("user", {}).get("name", "the user")
    projects = config.get("projects", [])
    agent_name = config.get("agent", {}).get("name", "the agent")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    projects_list = "\n".join(
        f"- {p['name']}: {p.get('description', 'active')}" for p in projects
    )

    # Read existing perfil as context if it exists
    agent_vault = Path(os.environ.get("AGENT_VAULT_PATH", ""))
    existing_perfil = ""
    if agent_vault.exists():
        perfil_path = agent_vault / "index" / "perfil-identidad.md"
        if perfil_path.exists():
            existing_perfil = perfil_path.read_text(encoding="utf-8", errors="ignore")[:2000]

    prompt = f"""You are updating the identity profile for {user_name}'s AI agent ({agent_name}).

This profile is used by the AI agent in every conversation to understand who {user_name} is.

Current projects:
{projects_list}

Previous profile (for reference):
{existing_perfil or '(none yet — this is the first run)'}

Generate an updated identity profile in Markdown. Include:

## Quién es {user_name}
(role, background, location, core drive — 3-4 sentences)

## Ventures Activos
(table: Venture | Description | Current Status)

## Objetivos Actuales
(top 3-5 goals right now — specific and measurable)

## Cómo Trabaja
(working style, preferences, communication style for the AI)

## Contexto Relevante
(anything the AI should keep in mind about {user_name}'s current situation)

Keep it factual and current. Update based on what you know from the projects list.
Date: {today}"""

    profile = call_llm(prompt)

    content = f"""---
title: Perfil de Identidad — {today}
type: identity-profile
date: {today}
---

{profile}

---
*Updated by perfil-identidad.py on {today}*
"""

    result = escribir_en_vault_sync(
        vault="agent",
        archivo="index/perfil-identidad.md",
        contenido=content,
        modo="actualizar",
        agente="perfil-identidad",
    )
    print(f"[perfil-identidad] {'✅' if result else '❌'} updated for {today}")


if __name__ == "__main__":
    main()
