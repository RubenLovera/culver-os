"""
CulverBrain v3.0 — Capa 5 (Interaction Memory) + Capa 6 (Action Memory)
Compartido por todos los bots del sistema.

Colecciones ChromaDB:
  {BRAIN_NAME}_interactions  — decisiones, compromisos, preguntas, patrones
  {BRAIN_NAME}_actions       — audit log de acciones de los bots
"""

import fcntl
import json
import os
import time
import uuid

import chromadb
import google.generativeai as genai

# ── Config ───────────────────────────────────────────────────────────────────

BRAIN_NAME = os.getenv("BRAIN_NAME", "culver")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CULVER_OS_DIR = os.getenv("CULVER_OS_DIR", "/root/culver-os")
ACTION_LOG_PATH = os.path.join(CULVER_OS_DIR, "action_log.jsonl")

INTERACTION_QUERY_THRESHOLD = 0.75
ACTION_QUERY_THRESHOLD = 0.75

PREFILER_KEYWORDS = [
    "decidí", "voy a", "hay que", "necesito", "quiero", "prometí",
    "debería", "me comprometo", "pendiente", "no sé", "?",
    "decided", "going to", "need to",
]

EXTRACTION_SYSTEM_PROMPT = """You are a memory extractor for a personal agent system.
Analyze the following exchange and extract ONLY if one of these 4 things is present:
- DECISION: something the user decided to do or not do
- COMMITMENT: something the user promised or plans to do (includes "I'll", "need to", "going to")
- QUESTION: a question that was left unresolved or pending investigation
- PATTERN: something the user mentioned that has appeared before (recurring signal)

If none of these are present, respond exactly: {"found": false}
If one is present, respond JSON with exactly these keys:
{"found": true, "content": "clear description in one sentence", "interaction_type": "decision|commitment|question|pattern", "topic": "work|finance|personal|system|other"}

Rules:
- Only extract if clear and unambiguous. When in doubt: {"found": false}
- content must be a complete, self-contained sentence (no references to "that" or "this")
- One turn of conversation has at most ONE extraction (the most important one)
- Greetings, confirmations, and casual conversation → {"found": false}
"""

# ── ChromaDB singleton ────────────────────────────────────────────────────────

_chroma_client = None


def _get_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return _chroma_client


def _get_interactions_collection():
    return _get_client().get_or_create_collection(
        name=f"{BRAIN_NAME}_interactions",
        metadata={"hnsw:space": "cosine"},
    )


def _get_actions_collection():
    return _get_client().get_or_create_collection(
        name=f"{BRAIN_NAME}_actions",
        metadata={"hnsw:space": "cosine"},
    )


# ── Capa 5: Interaction Memory ────────────────────────────────────────────────

def record_interaction(
    content: str,
    interaction_type: str,
    source_bot: str,
    topic: str,
    user_message: str = "",
    resolved: bool = False,
) -> str:
    """Escribe una interacción a ChromaDB {BRAIN_NAME}_interactions. Retorna doc_id."""
    doc_id = str(uuid.uuid4())
    now = time.time()
    collection = _get_interactions_collection()
    collection.add(
        ids=[doc_id],
        documents=[content],
        metadatas=[{
            "interaction_type": interaction_type,
            "source_bot": source_bot,
            "topic": topic,
            "date": time.strftime("%Y-%m-%d", time.localtime(now)),
            "timestamp": now,
            "resolved": resolved,
            "user_message": user_message[:500],
        }],
    )
    return doc_id


def query_interactions(
    text: str,
    n: int = 5,
    interaction_type: str = None,
    resolved: bool = False,
) -> list[dict]:
    """Query semántico a Capa 5. Retorna lista de dicts con document + metadata."""
    collection = _get_interactions_collection()
    where = {"resolved": resolved}
    if interaction_type:
        where["interaction_type"] = interaction_type
    try:
        results = collection.query(
            query_texts=[text],
            n_results=n,
            where=where,
        )
    except Exception:
        return []

    out = []
    if not results["ids"] or not results["ids"][0]:
        return out
    for i, doc_id in enumerate(results["ids"][0]):
        dist = results["distances"][0][i] if results.get("distances") else 1.0
        if dist < INTERACTION_QUERY_THRESHOLD:
            entry = {"id": doc_id, "document": results["documents"][0][i]}
            entry.update(results["metadatas"][0][i])
            out.append(entry)
    return out


def get_open_commitments(n: int = 10) -> list[dict]:
    """Compromisos sin resolver, ordenados por timestamp desc."""
    collection = _get_interactions_collection()
    try:
        results = collection.get(
            where={"$and": [{"resolved": False}, {"interaction_type": "commitment"}]},
            limit=n,
        )
    except Exception:
        return []
    if not results["ids"]:
        return []
    out = []
    for i, doc_id in enumerate(results["ids"]):
        entry = {"id": doc_id, "document": results["documents"][i]}
        entry.update(results["metadatas"][i])
        out.append(entry)
    out.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return out


def mark_resolved(doc_id: str):
    """Marca un compromiso como resuelto en ChromaDB."""
    collection = _get_interactions_collection()
    collection.update(ids=[doc_id], metadatas=[{"resolved": True}])


def extract_interaction(
    user_message: str,
    bot_response: str,
    source_bot: str,
) -> dict | None:
    """Pre-filtro sin LLM → Gemini call ligero si pasa el filtro.
    Retorna dict compatible con **kwargs de record_interaction(), o None.
    """
    msg = user_message.strip()
    if len(msg) < 15:
        return None
    msg_lower = msg.lower()
    if not any(kw in msg_lower for kw in PREFILER_KEYWORDS):
        return None
    if not GEMINI_API_KEY:
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)

    few_shot = (
        "Examples:\n"
        'User: "I\'m going to pause all work on Project X this month"\n'
        '→ {"found": true, "content": "User decided to pause Project X operations this month", '
        '"interaction_type": "commitment", "topic": "work"}\n\n'
        'User: "Do you know how much I spent on the VPS this month?"\n'
        '→ {"found": true, "content": "User wants to know VPS spending for this month", '
        '"interaction_type": "question", "topic": "system"}\n\n'
        'User: "ok thanks"\n'
        '→ {"found": false}\n\n'
    )
    prompt = (
        f"{few_shot}"
        f'User: "{user_message}"\n'
        f'Bot: "{bot_response[:300]}"\n'
        "Extract if applicable:"
    )

    try:
        response = model.generate_content(
            EXTRACTION_SYSTEM_PROMPT + "\n\n" + prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text.strip())
    except Exception:
        return None

    if not data.get("found"):
        return None

    return {
        "content": data.get("content", ""),
        "interaction_type": data.get("interaction_type", "decision"),
        "topic": data.get("topic", "other"),
        "user_message": user_message,
    }


# ── Capa 6: Action Memory ─────────────────────────────────────────────────────

def record_action(
    action_type: str,
    source_bot: str,
    content: str,
    outcome: str = "pending",
    message_id: int = None,
) -> str:
    """Escribe a action_log.jsonl (fcntl.flock) + ChromaDB {BRAIN_NAME}_actions.
    Retorna action_id (UUID).
    flock garantiza escrituras atómicas cuando varios bots corren como procesos separados.
    """
    action_id = str(uuid.uuid4())
    now = time.time()
    entry = {
        "action_id": action_id,
        "action_type": action_type,
        "source_bot": source_bot,
        "content": content[:500],
        "outcome": outcome,
        "timestamp": now,
        "date": time.strftime("%Y-%m-%d", time.localtime(now)),
        "message_id": message_id,
    }

    with open(ACTION_LOG_PATH, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    try:
        collection = _get_actions_collection()
        collection.add(
            ids=[action_id],
            documents=[content],
            metadatas=[{
                "action_type": action_type,
                "source_bot": source_bot,
                "outcome": outcome,
                "timestamp": now,
                "date": entry["date"],
                "message_id": message_id if message_id is not None else -1,
            }],
        )
    except Exception:
        pass  # JSONL es la fuente de verdad — ChromaDB es best-effort

    return action_id


def mark_acknowledged(action_id: str):
    """Actualiza outcome='acknowledged' en JSONL + ChromaDB."""
    _update_jsonl_outcome(action_id, "acknowledged")
    try:
        _get_actions_collection().update(
            ids=[action_id],
            metadatas=[{"outcome": "acknowledged"}],
        )
    except Exception:
        pass


def mark_acknowledged_by_message_id(message_id: int):
    """Busca en action_log.jsonl por message_id y marca como acknowledged.
    O(n) — aceptable para volumen normal (<100 acciones/día).
    """
    if not os.path.exists(ACTION_LOG_PATH):
        return
    with open(ACTION_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("message_id") == message_id and entry.get("outcome") == "pending":
                    mark_acknowledged(entry["action_id"])
                    return
            except Exception:
                continue


def get_unacknowledged(source_bot: str = None, days: int = 3) -> list[dict]:
    """Lee action_log.jsonl — filtra outcome='pending' AND timestamp reciente."""
    if not os.path.exists(ACTION_LOG_PATH):
        return []
    cutoff = time.time() - days * 86400
    out = []
    with open(ACTION_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("outcome") != "pending":
                    continue
                if entry.get("timestamp", 0) < cutoff:
                    continue
                if source_bot and entry.get("source_bot") != source_bot:
                    continue
                out.append(entry)
            except Exception:
                continue
    return out


def query_actions(text: str, n: int = 5) -> list[dict]:
    """Query semántico a Capa 6 via ChromaDB {BRAIN_NAME}_actions."""
    collection = _get_actions_collection()
    try:
        results = collection.query(query_texts=[text], n_results=n)
    except Exception:
        return []

    out = []
    if not results["ids"] or not results["ids"][0]:
        return out
    for i, doc_id in enumerate(results["ids"][0]):
        dist = results["distances"][0][i] if results.get("distances") else 1.0
        if dist < ACTION_QUERY_THRESHOLD:
            entry = {"id": doc_id, "document": results["documents"][0][i]}
            entry.update(results["metadatas"][0][i])
            out.append(entry)
    return out


# ── Helpers internos ──────────────────────────────────────────────────────────

def _update_jsonl_outcome(action_id: str, new_outcome: str):
    """Reescribe action_log.jsonl actualizando el outcome del action_id dado."""
    if not os.path.exists(ACTION_LOG_PATH):
        return
    lines = []
    updated = False
    with open(ACTION_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                lines.append(line)
                continue
            try:
                entry = json.loads(stripped)
                if entry.get("action_id") == action_id:
                    entry["outcome"] = new_outcome
                    lines.append(json.dumps(entry, ensure_ascii=False) + "\n")
                    updated = True
                else:
                    lines.append(line if line.endswith("\n") else line + "\n")
            except Exception:
                lines.append(line if line.endswith("\n") else line + "\n")

    if updated:
        with open(ACTION_LOG_PATH, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.writelines(lines)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
