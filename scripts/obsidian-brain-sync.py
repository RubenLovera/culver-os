"""
obsidian-brain-sync.py — Indexes the personal vault into ChromaDB.

Reads all .md files from the personal vault (git pull first),
indexes only files modified since last run (mtime-based).
Runs every 2 hours via systemd timer.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env.admin"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent.parent))

import tools.obsidian as obsidian

LAST_SYNC_FILE = Path("/tmp/obsidian-brain-last-sync")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100


def get_last_sync() -> float:
    if LAST_SYNC_FILE.exists():
        try:
            return float(LAST_SYNC_FILE.read_text().strip())
        except Exception:
            pass
    return 0.0


def save_last_sync(ts: float):
    LAST_SYNC_FILE.write_text(str(ts))


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + size])
        chunks.append(chunk)
        i += size - overlap
    return chunks


def main():
    import chromadb

    vault_path = Path(os.environ["PERSONAL_VAULT_PATH"])
    brain_name = os.environ.get("BRAIN_NAME", "culver_brain")

    print(f"[obsidian-brain-sync] pulling personal vault...")
    obsidian.pull("personal")

    last_sync = get_last_sync()
    run_start = time.time()

    client = chromadb.HttpClient(host="localhost", port=8000)
    collection = client.get_or_create_collection(brain_name)

    md_files = list(vault_path.rglob("*.md"))
    updated = [f for f in md_files if f.stat().st_mtime > last_sync]

    if not updated:
        print(f"[obsidian-brain-sync] nothing new since last run")
        save_last_sync(run_start)
        return

    print(f"[obsidian-brain-sync] indexing {len(updated)} files...")
    indexed = 0

    for md_file in updated:
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = str(md_file.relative_to(vault_path))
            chunks = chunk_text(content)

            for i, chunk in enumerate(chunks):
                doc_id = f"personal::{rel_path}::{i}"
                collection.upsert(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[{"source": rel_path, "vault": "personal", "chunk": i, "type": "obsidian"}],
                )
            indexed += 1
        except Exception as e:
            print(f"[obsidian-brain-sync] ⚠️ skipped {md_file.name}: {e}")

    save_last_sync(run_start)
    print(f"[obsidian-brain-sync] ✅ indexed {indexed}/{len(updated)} files")


if __name__ == "__main__":
    main()
