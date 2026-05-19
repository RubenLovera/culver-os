"""
connectors/obsidian_sync.py — Copies selected folders from the personal vault to raw/.

This is the only pre-built connector in the MVP. It makes personal vault content
(Daily Notes, Weekly Reviews, etc.) available for ingestion into the agent vault wiki.

Config section in config.json:
    "connectors": {
        "obsidian_sync": {
            "sync_folders": ["Daily Notes", "Weekly Reviews"],
            "max_days": 30
        }
    }

sync_folders: list of folder names to copy from personal vault
max_days:     only copy files modified in the last N days (default: 30)
"""

import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from connectors.base import BaseConnector, DepositedFile


class ObsidianSyncConnector(BaseConnector):

    def name(self) -> str:
        return "obsidian_sync"

    def validate_config(self, config: dict) -> bool:
        personal_path = os.environ.get("PERSONAL_VAULT_PATH")
        if not personal_path:
            print("[obsidian_sync] ERROR: PERSONAL_VAULT_PATH not set")
            return False
        if not Path(personal_path).exists():
            print(f"[obsidian_sync] ERROR: personal vault not found at {personal_path}")
            return False
        sync_folders = config.get("sync_folders", [])
        if not sync_folders:
            print("[obsidian_sync] WARNING: no sync_folders configured")
        return True

    def run(self, config: dict, raw_dir: str) -> list[DepositedFile]:
        personal_path = Path(os.environ["PERSONAL_VAULT_PATH"])
        dest_dir = Path(raw_dir) / "personal_vault_sync"
        dest_dir.mkdir(parents=True, exist_ok=True)

        sync_folders = config.get("sync_folders", ["Daily Notes"])
        max_days = config.get("max_days", 30)
        cutoff = time.time() - (max_days * 86400)

        deposited = []

        for folder_name in sync_folders:
            src_folder = personal_path / folder_name
            if not src_folder.exists():
                print(f"[obsidian_sync] folder not found: {folder_name} — skipping")
                continue

            dst_folder = dest_dir / folder_name
            dst_folder.mkdir(parents=True, exist_ok=True)

            for md_file in sorted(src_folder.rglob("*.md")):
                if md_file.stat().st_mtime < cutoff:
                    continue
                rel_path = md_file.relative_to(personal_path)
                dst_path = dest_dir / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)

                content = md_file.read_text(encoding="utf-8", errors="ignore")
                dst_path.write_text(content, encoding="utf-8")

                deposited.append(DepositedFile(
                    path=str(Path("personal_vault_sync") / rel_path),
                    content=content,
                    title=md_file.stem,
                ))

        print(f"[obsidian_sync] ✅ synced {len(deposited)} files from {len(sync_folders)} folders")
        return deposited
