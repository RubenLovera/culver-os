"""
CulverBrain — Capa 3 (Semantic Memory)
Query al vector store ChromaDB. BRAIN_NAME se configura via env.
"""

import os
import chromadb

BRAIN_NAME = os.getenv("BRAIN_NAME", "culver")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
QUERY_THRESHOLD = 0.7

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return _client


def query(text: str, venture: str = None, top_n: int = 5):
    """Query semántico a la colección {BRAIN_NAME}_brain."""
    client = get_client()
    collection = client.get_collection(f"{BRAIN_NAME}_brain")
    where = {"venture": venture} if venture else None
    results = collection.query(
        query_texts=[text],
        n_results=top_n,
        where=where,
    )
    return results


def query_filtered(text: str, top_n: int = 5) -> list[dict]:
    """Query con filtro por threshold. Retorna chunks relevantes."""
    results = query(text, top_n=top_n)
    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    out = []
    for doc, dist, meta in zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0],
    ):
        if dist < QUERY_THRESHOLD:
            out.append({"document": doc, "distance": dist, "metadata": meta})
    return out
