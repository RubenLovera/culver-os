"""
connectors/granola.py — Ingests Granola meeting transcripts into raw/.

Granola runs on Mac, not on the VPS, so this connector works via a sync folder:
a directory in your personal vault (or anywhere git-synced) where Granola
transcripts land. The connector reads .md files from that folder.

Two ways to populate the sync folder:
  1. Obsidian plugin: set Granola to export to your Obsidian vault, then
     let obsidian_sync pick it up (no extra connector needed).
  2. Script: run tools/export_granola.py on your Mac — it calls the local
     Granola API and writes transcripts to the configured export_dir.

Config section in config.json:
    "connectors": {
        "granola": {
            "export_dir": "/path/to/granola-exports",
            "max_days": 30
        }
    }

No API key required — reads from a local directory on the VPS.
The export_dir must be accessible on the VPS (e.g. synced via git or rsync).
"""

import time
from pathlib import Path

from connectors.base import BaseConnector, DepositedFile


class GranolaConnector(BaseConnector):

    def name(self) -> str:
        return "granola"

    def validate_config(self, config: dict) -> bool:
        export_dir = config.get("export_dir")
        if not export_dir:
            print("[granola] ERROR: export_dir not set in config")
            return False
        if not Path(export_dir).exists():
            print(f"[granola] ERROR: export_dir not found: {export_dir}")
            return False
        return True

    def run(self, config: dict, raw_dir: str) -> list[DepositedFile]:
        export_dir = Path(config["export_dir"])
        max_days = config.get("max_days", 30)
        cutoff = time.time() - (max_days * 86400)

        dest_dir = Path(raw_dir) / "granola"
        dest_dir.mkdir(parents=True, exist_ok=True)

        deposited = []
        for md_file in sorted(export_dir.rglob("*.md")):
            if md_file.stat().st_mtime < cutoff:
                continue
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            dest = dest_dir / md_file.name
            dest.write_text(content, encoding="utf-8")
            deposited.append(DepositedFile(
                path=str(dest.relative_to(raw_dir)),
                content=content,
                title=md_file.stem,
            ))

        print(f"[granola] ✅ {len(deposited)} transcripts from {export_dir}")
        return deposited
