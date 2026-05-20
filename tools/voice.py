"""Voice note processing via Gemini Audio (multimodal).

Requires GEMINI_API_KEY env var. Uses google-genai SDK.
The ventures list for area detection is read from config.json (daily_note.ventures).
"""
import os
import json
import logging
import tempfile
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _ventures() -> list[str]:
    path = os.environ.get("CONFIG_PATH", "/culver-os/config.json")
    try:
        with open(path) as f:
            return json.load(f).get("daily_note", {}).get("ventures", [])
    except Exception:
        return []


def _extract_prompt() -> str:
    ventures = _ventures()
    ventures_hint = ", ".join(ventures) if ventures else "any area"
    return f"""Transcribe this audio and extract structured information as JSON with these fields:

{{
  "transcription": "full text of the audio",
  "tasks": ["task 1", "task 2"],
  "ideas": ["idea 1"],
  "decisions": ["decision 1"],
  "wins": ["achievement 1"],
  "pending": ["pending item 1"],
  "learned": "what was learned (string)",
  "energy_level": null,
  "peso": null,
  "calorias": null,
  "gastos": [],
  "ingresos": [],
  "area": ""
}}

Rules:
- energy_level: number 1-10 if mentioned, otherwise null
- peso: weight in kg if mentioned, otherwise null
- calorias: calories if mentioned, otherwise null
- gastos: list of strings with expenses mentioned
- ingresos: list of strings with income mentioned
- area: if the audio clearly belongs to a specific area ({ventures_hint}), set it. Otherwise empty string.
- Return ONLY the JSON, no extra text.
"""


async def process_voice_note(audio_bytes: bytes, mime_type: str = "audio/ogg") -> dict:
    """Process a voice note via Gemini Audio. Returns structured dict."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY not configured", "transcription": ""}

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        return {"ok": False, "error": "google-genai not installed: pip install google-genai", "transcription": ""}

    client = genai.Client(api_key=api_key)
    tmp_path = None
    uploaded = None
    raw = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        uploaded = await asyncio.to_thread(
            client.files.upload,
            file=tmp_path,
            config=genai_types.UploadFileConfig(mime_type=mime_type),
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[uploaded, _extract_prompt()],
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])

        result = json.loads(raw)
        result["ok"] = True
        return result

    except json.JSONDecodeError as e:
        logger.error("Voice: JSON parse error: %s | raw: %s", e, raw[:200])
        return {"ok": False, "error": f"JSON parse error: {e}", "transcription": raw}
    except Exception as e:
        logger.error("Voice: processing error: %s", e)
        return {"ok": False, "error": str(e), "transcription": ""}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        if uploaded:
            try:
                await asyncio.to_thread(client.files.delete, name=uploaded.name)
            except Exception:
                pass


def summarize_extraction(result: dict) -> str:
    """Return a short human-readable summary of what was extracted."""
    if not result.get("ok"):
        return f"❌ Could not process audio: {result.get('error', 'unknown error')}"

    parts = []
    if result.get("tasks"):    parts.append(f"{len(result['tasks'])} task(s)")
    if result.get("ideas"):    parts.append(f"{len(result['ideas'])} idea(s)")
    if result.get("decisions"):parts.append(f"{len(result['decisions'])} decision(s)")
    if result.get("wins"):     parts.append(f"{len(result['wins'])} win(s)")
    if result.get("peso"):     parts.append(f"weight: {result['peso']} kg")
    if result.get("energy_level"): parts.append(f"energy: {result['energy_level']}/10")

    if not parts:
        return "✅ Audio transcribed (no structured items detected)"
    return "✅ Saved: " + ", ".join(parts)
