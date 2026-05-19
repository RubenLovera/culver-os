"""
vault-ingest.py — raw/ → LLM → wiki/ pipeline for the agent vault.

Flow:
  1. Run enabled connectors (deposit files into raw/)
  2. Detect files in raw/ not yet in index/log.md
  3. For each new file (up to MAX_PER_RUN): call LLM → generate wiki page
  4. Update MASTER_INDEX.md
  5. Append entries to index/log.md
  6. Push all changes via vault_writer.py (GitHub API)

Runs daily at 12:00 UTC via systemd timer.
Can also be triggered manually with /culver-ingest skill.
"""

import importlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env.admin"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.llm import call_llm
from tools.vault_writer import escribir_en_vault_sync

MAX_PER_RUN = int(os.environ.get("VAULT_INGEST_MAX_PER_RUN", "10"))


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)


def get_agent_vault_path() -> Path:
    path = os.environ.get("AGENT_VAULT_PATH")
    if not path:
        raise EnvironmentError("AGENT_VAULT_PATH not set")
    return Path(path)


def git_pull(vault_path: Path):
    subprocess.run(
        ["git", "-C", str(vault_path), "pull", "--rebase"],
        check=True, capture_output=True, timeout=30,
    )


def read_log(vault_path: Path) -> set[str]:
    """Return set of filenames already mentioned in index/log.md."""
    log_path = vault_path / "index" / "log.md"
    if not log_path.exists():
        return set()
    content = log_path.read_text(encoding="utf-8")
    # Lines like: ## [2026-05-18] ingest | filename.md
    return set(re.findall(r"\| (.+\.md)", content))


def find_new_raw_files(vault_path: Path, processed: set[str]) -> list[Path]:
    raw_path = vault_path / "raw"
    if not raw_path.exists():
        return []
    all_raw = sorted(raw_path.rglob("*.md"), key=lambda f: f.stat().st_mtime)
    new_files = []
    for f in all_raw:
        rel = str(f.relative_to(vault_path / "raw"))
        if rel not in processed and f.name not in processed:
            new_files.append(f)
    return new_files


def extract_frontmatter(content: str) -> dict:
    meta = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm = content[3:end].strip()
            for line in fm.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"')
    return meta


def determine_topic(file_path: Path, config: dict) -> str:
    """Map raw file to a wiki topic folder based on config topics or filename heuristics."""
    topics = config.get("agent_vault", {}).get("topics", [])
    name_lower = file_path.stem.lower()
    parent_lower = file_path.parent.name.lower()

    for topic in topics:
        if topic.lower() in name_lower or topic.lower() in parent_lower:
            return topic.lower().replace(" ", "-")

    # Fallback: use the raw subdirectory name
    parts = file_path.parts
    if len(parts) >= 2:
        return parts[0].replace("_", "-")
    return "general"


def generate_wiki_page(raw_content: str, source_file: Path, config: dict) -> tuple[str, str]:
    """
    Call LLM to generate a wiki page from raw content.
    Returns (wiki_content, suggested_filename).
    """
    meta = extract_frontmatter(raw_content)
    title = meta.get("title", source_file.stem)
    source_url = meta.get("source", "")
    date = meta.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    user_name = config.get("user", {}).get("name", "the user")
    agent_name = config.get("agent", {}).get("name", "the agent")

    prompt = f"""You are the knowledge compiler for {user_name}'s personal AI system ({agent_name}).

Your job: transform the raw source below into a structured wiki page in Markdown.

Rules:
- Extract key facts, decisions, insights, and action items
- Write in third person ("The user...", "The project...")
- Use ## sections for: Summary, Key Points, Decisions, Action Items, Links
- Include frontmatter with title, type, date, source, status: raw
- Be concise but complete — this page will be indexed in a vector database
- Do NOT include raw conversational filler or metadata noise
- Output ONLY the markdown, no commentary

Source file: {source_file.name}
Source URL: {source_url or 'N/A'}
Date: {date}

---RAW CONTENT---
{raw_content[:6000]}
---END---

Generate the wiki page now:"""

    wiki_content = call_llm(prompt)

    # Generate filename from title
    safe_name = re.sub(r"[^\w\s-]", "", title.lower())
    safe_name = re.sub(r"\s+", "-", safe_name.strip())[:60]
    filename = f"{date}-{safe_name}.md"

    return wiki_content, filename



def run_connectors(config: dict, vault_path: Path):
    enabled = config.get("connectors", {}).get("enabled", [])
    raw_dir = str(vault_path / "raw")

    for connector_name in enabled:
        try:
            module = importlib.import_module(f"connectors.{connector_name}")
            # Find the connector class (subclass of BaseConnector)
            connector_cls = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and attr_name != "BaseConnector"
                        and hasattr(attr, "run") and hasattr(attr, "name")):
                    connector_cls = attr
                    break
            if not connector_cls:
                print(f"[vault-ingest] ⚠️ no connector class found in {connector_name}")
                continue
            connector = connector_cls()
            connector_config = config.get("connectors", {}).get(connector_name, {})
            if not connector.validate_config(connector_config):
                print(f"[vault-ingest] ⚠️ {connector_name} config invalid — skipping")
                continue
            connector.run(connector_config, raw_dir)
        except Exception as e:
            print(f"[vault-ingest] ⚠️ connector {connector_name} failed: {e}")


def main():
    config = load_config()
    vault_path = get_agent_vault_path()

    print(f"[vault-ingest] pulling agent vault...")
    git_pull(vault_path)

    # Run connectors to deposit new files into raw/
    run_connectors(config, vault_path)

    # Detect new raw files
    processed = read_log(vault_path)
    new_files = find_new_raw_files(vault_path, processed)

    if not new_files:
        print(f"[vault-ingest] nothing new in raw/ — done")
        return

    batch = new_files[:MAX_PER_RUN]
    print(f"[vault-ingest] processing {len(batch)}/{len(new_files)} new files...")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_entries = []
    master_index_content = None
    wiki_writes = []

    for raw_file in batch:
        try:
            raw_content = raw_file.read_text(encoding="utf-8", errors="ignore")
            if len(raw_content.strip()) < 50:
                print(f"[vault-ingest] ⏭ skipping {raw_file.name} (too short)")
                log_entries.append(f"\n## [{today}] ingest | {raw_file.name} — skipped (too short)\n")
                continue

            meta = extract_frontmatter(raw_content)
            title = meta.get("title", raw_file.stem)
            topic = determine_topic(raw_file, config)

            print(f"[vault-ingest] generating wiki page for: {raw_file.name}")
            wiki_content, wiki_filename = generate_wiki_page(raw_content, raw_file, config)

            wiki_rel_path = f"wiki/{topic}/{wiki_filename}"
            wiki_writes.append((wiki_rel_path, wiki_content, title, topic))
            log_entries.append(f"\n## [{today}] ingest | {raw_file.name}\n**Generated:** {wiki_rel_path}\n")

        except Exception as e:
            print(f"[vault-ingest] ❌ failed {raw_file.name}: {e}")
            log_entries.append(f"\n## [{today}] ingest | {raw_file.name} — ERROR: {e}\n")

    # Push wiki pages
    for wiki_path, wiki_content, title, topic in wiki_writes:
        ok = escribir_en_vault_sync(
            vault="agent",
            archivo=wiki_path,
            contenido=wiki_content,
            modo="crear",
            agente="vault-ingest",
        )
        if ok:
            # Update MASTER_INDEX content in memory
            vault_copy = vault_path  # for index update tracking
            print(f"[vault-ingest] ✅ wrote {wiki_path}")

    # Update MASTER_INDEX.md
    if wiki_writes:
        index_path = vault_path / "index" / "MASTER_INDEX.md"
        updated_index = index_path.read_text(encoding="utf-8") if index_path.exists() else "# MASTER INDEX\n\n"
        for wiki_path, _, title, topic in wiki_writes:
            entry = f"- [{title}]({wiki_path}) — {today}"
            section_header = f"## {topic.title()}"
            if section_header in updated_index:
                idx = updated_index.index(section_header) + len(section_header)
                next_section = updated_index.find("\n## ", idx)
                insert_at = next_section if next_section != -1 else len(updated_index)
                updated_index = updated_index[:insert_at].rstrip() + f"\n{entry}\n" + updated_index[insert_at:]
            else:
                updated_index = updated_index.rstrip() + f"\n\n{section_header}\n{entry}\n"

        escribir_en_vault_sync(
            vault="agent",
            archivo="index/MASTER_INDEX.md",
            contenido=updated_index,
            modo="actualizar",
            agente="vault-ingest",
        )

    # Append to log.md
    if log_entries:
        log_content = "\n".join(log_entries)
        escribir_en_vault_sync(
            vault="agent",
            archivo="index/log.md",
            contenido=log_content,
            modo="agregar",
            agente="vault-ingest",
        )

    # Update RECENT_UPDATES.md
    recent_content = f"""---
title: RECENT UPDATES — Agent Vault
type: index
updated: {today}
---

# RECENT UPDATES — {today}

> Last ingestion cycle. Auto-updated.

## Cycle: {today}

### Processed
{chr(10).join(f"- {wp}" for wp, _, _, _ in wiki_writes) or "- (none)"}

### Stats
- **Files processed:** {len(batch)}
- **Wiki pages created:** {len(wiki_writes)}
- **Remaining in queue:** {max(0, len(new_files) - MAX_PER_RUN)}

---
**Next cycle:** tomorrow at 12:00 UTC
"""
    escribir_en_vault_sync(
        vault="agent",
        archivo="index/RECENT_UPDATES.md",
        contenido=recent_content,
        modo="actualizar",
        agente="vault-ingest",
    )

    print(f"[vault-ingest] ✅ done — {len(wiki_writes)} wiki pages created")


if __name__ == "__main__":
    main()
