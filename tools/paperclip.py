"""Paperclip governance — LLM cost reporting.

All config via env vars — never blocks, fire-and-forget.

Required env vars (set per-bot in .env.{bot}):
  PAPERCLIP_URL      — base URL of your Paperclip instance (default: http://localhost:58209/api)
  PAPERCLIP_COMPANY_ID — company UUID in Paperclip
  PCP_AGENT_ID       — agent UUID for this bot
  PCP_TOKEN          — bearer token for this bot
"""
import os
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def report_cost(
    provider: str,
    model: str,
    cost_cents: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Report LLM cost to Paperclip. Never raises — silently no-ops if not configured."""
    base_url    = os.environ.get("PAPERCLIP_URL", "http://localhost:58209/api")
    company_id  = os.environ.get("PAPERCLIP_COMPANY_ID", "")
    agent_id    = os.environ.get("PCP_AGENT_ID", "")
    token       = os.environ.get("PCP_TOKEN", "")

    if not all([company_id, agent_id, token]):
        return

    try:
        requests.post(
            f"{base_url}/companies/{company_id}/cost-events",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": base_url.rsplit("/api", 1)[0],
                "Content-Type": "application/json",
            },
            json={
                "agentId": agent_id,
                "provider": provider,
                "model": model,
                "costCents": cost_cents,
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            timeout=2,
        )
    except Exception:
        pass
