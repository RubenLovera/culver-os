"""
vault-brain-sync.py — Indexes wiki/ changes from agent vault into ChromaDB.

Uses git diff to detect only changed files since last sync (incremental).
Runs daily at 14:00 UTC via systemd timer, and after vault-ingest.py writes.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env.admin"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent.parent))

LAST_SYNC_FILE = Path("/tmp/vault-brain-last-sync-commit")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100


def git_pull(vault_path: str):
    subprocess.run(
        ["git", "-C", vault_path, "pull", "--rebase"],
        check=True, capture_output=True, timeout=30,
    )


def get_last_commit() -> str:
    if LAST_SYNC_FILE.exists():
        return LAST_SYNC_FILE.read_text().strip()
    return ""


def save_last_commit(commit: str):
    LAST_SYNC_FILE.write_text(commit)


def get_current_commit(vault_path: str) -> str:
    r = subprocess.run(
        ["git", "-C", vault_path, "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    return r.stdout.strip()


def get_changed_wiki_files(vault_path: str, since_commit: str) -> list[str]:
    if not since_commit:
        # First run: index all wiki/ files
        wiki_path = Path(vault_path) / "wiki"
        if not wiki_path.exists():
            return []
        return [str(f.relative_to(vault_path)) for f in wiki_path.rglob("*.md")]

    r = subprocess.run(
        ["git", "-C", vault_path, "diff", "--name-only", since_commit, "HEAD", "--", "wiki/"],
        capture_output=True, text=True, timeout=15,
    )
    return [line for line in r.stdout.strip().splitlines() if line.endswith(".md")]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + size]))
        i += size - overlap
    return chunks


def main():
    import chromadb

    vault_path = os.environ["AGENT_VAULT_PATH"]
    brain_name = os.environ.get("BRAIN_NAME", "culver_brain")

    print(f"[vault-brain-sync] pulling agent vault...")
    git_pull(vault_path)

    last_commit = get_last_commit()
    current_commit = get_current_commit(vault_path)

    if last_commit == current_commit:
        print(f"[vault-brain-sync] no changes since last sync ({current_commit[:8]})")
        return

    changed = get_changed_wiki_files(vault_path, last_commit)
    if not changed:
        save_last_commit(current_commit)
        print(f"[vault-brain-sync] no wiki/ changes")
        return

    print(f"[vault-brain-sync] indexing {len(changed)} changed wiki files...")
    client = chromadb.HttpClient(host="localhost", port=8000)
    collection = client.get_or_create_collection(brain_name)
    indexed = 0

    for rel_path in changed:
        full_path = Path(vault_path) / rel_path
        if not full_path.exists():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_text(content)
            for i, chunk in enumerate(chunks):
                doc_id = f"agent::{rel_path}::{i}"
                collection.upsert(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[{"source": rel_path, "vault": "agent", "chunk": i, "type": "wiki"}],
                )
            indexed += 1
        except Exception as e:
            print(f"[vault-brain-sync] ⚠️ skipped {rel_path}: {e}")

    save_last_commit(current_commit)
    print(f"[vault-brain-sync] ✅ indexed {indexed}/{len(changed)} files (commit {current_commit[:8]})")


if __name__ == "__main__":
    main()
