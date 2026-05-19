"""
vault_writer.py — GitHub API writer for CulverOS framework.

Writes files to GitHub without git clone in the VPS process.
Preferred for timer scripts (avoids merge conflicts from parallel git ops).

For bot conversations that need immediate local access, use tools/obsidian.py instead.
"""

import asyncio
import base64
import fcntl
import logging
import os
import re
import subprocess
import time
from typing import Optional

import requests

GITHUB_API = "https://api.github.com"
LOCK_PATH = "/tmp/vault-writer.lock"

_write_lock = asyncio.Lock()
_token_cache: Optional[str] = None

logger = logging.getLogger(__name__)


def _github_user() -> str:
    user = os.environ.get("GITHUB_USERNAME")
    if not user:
        raise EnvironmentError("GITHUB_USERNAME not set in environment")
    return user


def _github_token() -> str:
    global _token_cache
    if _token_cache:
        return _token_cache
    token = os.environ.get("GITHUB_PAT")
    if token:
        _token_cache = token
        return token
    # Fallback: extract from git remote URL of agent vault
    agent_path = os.environ.get("AGENT_VAULT_PATH", "")
    if agent_path:
        try:
            url = subprocess.check_output(
                ["git", "-C", agent_path, "remote", "get-url", "origin"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            extracted = url.split("@")[0].replace("https://", "")
            if extracted:
                _token_cache = extracted
                return extracted
        except Exception:
            pass
    raise EnvironmentError("GITHUB_PAT not set and could not be extracted from git remote")


def _vault_repo(vault: str) -> str:
    if vault == "personal":
        repo = os.environ.get("PERSONAL_VAULT_REPO")
    elif vault == "agent":
        repo = os.environ.get("AGENT_VAULT_REPO")
    else:
        raise ValueError(f"Unknown vault: '{vault}'. Use 'personal' or 'agent'.")
    if not repo:
        raise EnvironmentError(f"{'PERSONAL' if vault == 'personal' else 'AGENT'}_VAULT_REPO not set")
    # Accept "username/repo" or just "repo"
    if "/" not in repo:
        repo = f"{_github_user()}/{repo}"
    return repo


def _headers() -> dict:
    return {
        "Authorization": f"token {_github_token()}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }


def _gh_get(repo: str, path: str) -> Optional[dict]:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    r = requests.get(url, headers=_headers(), timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _gh_put(repo: str, path: str, content: str, message: str, sha: Optional[str] = None) -> dict:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    body: dict = {"message": message, "content": encoded}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()


def _apply_section_update(content: str, section: str, new_content: str) -> str:
    """Replace ## {section} body with new_content. Appends section if missing."""
    lines = content.split("\n")
    pattern = re.compile(rf"^## {re.escape(section)}\s*$")
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if pattern.match(line):
            start_idx = i
        elif start_idx is not None and i > start_idx and re.match(r"^## ", line):
            end_idx = i
            break
    if start_idx is None:
        return content.rstrip() + f"\n\n## {section}\n\n{new_content.strip()}\n"
    end_idx = end_idx if end_idx is not None else len(lines)
    result = lines[:start_idx] + [lines[start_idx], "", new_content.strip(), ""] + lines[end_idx:]
    return "\n".join(result)


def _write_sync(
    vault: str,
    archivo: str,
    contenido: str,
    seccion: Optional[str],
    modo: str,
    agente: str,
) -> bool:
    repo = _vault_repo(vault)
    backoffs = [5, 15, 30]

    with open(LOCK_PATH, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            for attempt, backoff in enumerate(backoffs + [None], 1):
                try:
                    existing = _gh_get(repo, archivo)

                    if modo == "crear":
                        if existing:
                            logger.error(f"[{agente}] crear: {archivo} already exists in {repo}")
                            return False
                        final_content = contenido
                        sha = None

                    elif modo == "agregar":
                        if existing:
                            current = base64.b64decode(
                                existing["content"].replace("\n", "")
                            ).decode("utf-8")
                            final_content = current.rstrip() + "\n\n" + contenido.strip() + "\n"
                            sha = existing["sha"]
                        else:
                            final_content = contenido
                            sha = None

                    else:  # actualizar (default)
                        if existing:
                            current = base64.b64decode(
                                existing["content"].replace("\n", "")
                            ).decode("utf-8")
                            sha = existing["sha"]
                            final_content = _apply_section_update(current, seccion, contenido) if seccion else contenido
                        else:
                            final_content = contenido
                            sha = None

                    commit_msg = f"chore({agente}): {modo} {archivo.split('/')[-1]}"
                    _gh_put(repo, archivo, final_content, commit_msg, sha)
                    label = f" §{seccion}" if seccion else ""
                    logger.info(f"[{agente}] ✅ {modo} {repo}/{archivo}{label}")
                    return True

                except Exception as e:
                    if backoff is None:
                        logger.error(f"[{agente}] ❌ FAILED {repo}/{archivo}: {e}")
                        return False
                    logger.warning(f"[{agente}] attempt {attempt} failed ({e}) — retry in {backoff}s")
                    time.sleep(backoff)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    return False


async def escribir_en_vault(
    vault: str,
    archivo: str,
    contenido: str,
    seccion: Optional[str] = None,
    modo: str = "actualizar",
    agente: str = "unknown",
) -> bool:
    """
    Async writer. For use in bots and async contexts.

    vault:    "personal" | "agent"
    archivo:  path relative to vault root
    contenido: full content or section content
    seccion:  ## header (without ##) — only used in modo "actualizar"
    modo:     "crear" | "actualizar" | "agregar"
    agente:   agent name for commit messages
    """
    async with _write_lock:
        return await asyncio.to_thread(
            _write_sync, vault, archivo, contenido, seccion, modo, agente
        )


def escribir_en_vault_sync(
    vault: str,
    archivo: str,
    contenido: str,
    seccion: Optional[str] = None,
    modo: str = "actualizar",
    agente: str = "unknown",
) -> bool:
    """Sync wrapper of escribir_en_vault. For timer scripts (non-async)."""
    return _write_sync(vault, archivo, contenido, seccion, modo, agente)
