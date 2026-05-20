#!/usr/bin/env python3
"""
brain_index_incremental.py — Re-indexes changed wiki/ files into ChromaDB.
Receives a list of relative paths via stdin (one per line) or as arguments.

Env vars:
  AGENT_VAULT_PATH   — local path to the cloned agent vault
  CHROMA_HOST        — ChromaDB host (default: localhost)
  CHROMA_PORT        — ChromaDB port (default: 8000)
  BRAIN_NAME         — ChromaDB collection name (default: culver_brain)

Usage:
  echo "wiki/beetransfer/pricing.md" | python3 tools/brain_index_incremental.py
  python3 tools/brain_index_incremental.py wiki/beetransfer/pricing.md wiki/crypto/index.md
"""

import os
import sys

import chromadb

VAULT_PATH  = os.environ.get("AGENT_VAULT_PATH", "/root/culver-os/vaults/agent-vault")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
COLLECTION  = os.environ.get("BRAIN_NAME", "culver_brain")

MIN_WORDS    = 50
CHUNK_WORDS  = 300
OVERLAP_WORDS = 40

EXCLUDE_FILES = {"CLAUDE.md", "log.md", "RECENT_UPDATES.md", "MASTER_INDEX.md"}
INDEX_FILES   = {"status-operativo.md", "perfil-identidad.md"}


def detect_venture(path: str) -> str:
    """Infers venture from wiki/ subdirectory structure."""
    parts = path.lower().replace("\\", "/").split("/")
    for part in parts:
        clean = part.replace("-", "_")
        if part not in ("wiki", "raw", "index", "outputs"):
            return part.replace("_", "-")
    return "general"


def detect_type(path: str) -> str:
    filename = os.path.basename(path)
    return "index" if filename in INDEX_FILES else "wiki"


def chunk_text(text: str) -> list[str]:
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        return [text]
    chunks, start = [], 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - OVERLAP_WORDS
    return chunks


def index_file(collection, abs_path: str) -> int:
    if not os.path.exists(abs_path):
        existing = collection.get(where={"path": abs_path})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"  deleted: {os.path.basename(abs_path)} ({len(existing['ids'])} chunks)")
        return 0

    filename = os.path.basename(abs_path)
    if filename in EXCLUDE_FILES or not filename.endswith(".md"):
        return 0

    try:
        text = open(abs_path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"  [WARN] cannot read {abs_path}: {e}", file=sys.stderr)
        return 0

    if len(text.split()) < MIN_WORDS:
        return 0

    existing = collection.get(where={"path": abs_path})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    chunks  = chunk_text(text)
    venture = detect_venture(abs_path)
    mtime   = os.path.getmtime(abs_path)

    ids, docs, metas = [], [], []
    for i, chunk in enumerate(chunks):
        ids.append(f"{abs_path}::chunk{i}")
        docs.append(chunk)
        metas.append({
            "path": abs_path,
            "venture": venture,
            "type": detect_type(abs_path),
            "mtime": mtime,
            "chunk_id": i,
            "total_chunks": len(chunks),
        })

    collection.add(ids=ids, documents=docs, metadatas=metas)
    return len(chunks)


def main():
    if len(sys.argv) > 1:
        rel_paths = sys.argv[1:]
    else:
        rel_paths = [line.strip() for line in sys.stdin if line.strip()]

    if not rel_paths:
        print("No files to index.")
        sys.exit(0)

    client     = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = client.get_collection(COLLECTION)

    total_chunks = 0
    for rel_path in rel_paths:
        abs_path = os.path.join(VAULT_PATH, rel_path)
        n = index_file(collection, abs_path)
        if n > 0:
            print(f"  indexed: {os.path.basename(abs_path)} ({n} chunks)")
        total_chunks += n

    print(f"Done. {len(rel_paths)} files processed, {total_chunks} chunks updated.")
    print(f"Total in collection: {collection.count()} chunks")


if __name__ == "__main__":
    main()
