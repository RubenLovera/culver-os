"""
connectors/notion.py — Ingests Notion pages and database entries into raw/.

Config section in config.json:
    "connectors": {
        "notion": {
            "page_ids": ["page-id-1", "page-id-2"],
            "database_ids": ["db-id-1"],
            "max_db_pages": 100
        }
    }

Env: NOTION_API_KEY — create at https://www.notion.so/my-integrations
     Share each page/database with your integration before running.
"""

import os
from pathlib import Path

import requests

from connectors.base import BaseConnector, DepositedFile

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


class NotionConnector(BaseConnector):

    def name(self) -> str:
        return "notion"

    def validate_config(self, config: dict) -> bool:
        if not os.environ.get("NOTION_API_KEY"):
            print("[notion] ERROR: NOTION_API_KEY not set")
            return False
        if not config.get("page_ids") and not config.get("database_ids"):
            print("[notion] WARNING: no page_ids or database_ids configured")
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        }

    def _get(self, path: str) -> dict | None:
        try:
            r = requests.get(f"{API}{path}", headers=self._headers(), timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[notion] ERROR GET {path}: {e}")
            return None

    def _post(self, path: str, body: dict) -> dict | None:
        try:
            r = requests.post(f"{API}{path}", headers=self._headers(), json=body, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[notion] ERROR POST {path}: {e}")
            return None

    def _rich_text(self, segments: list) -> str:
        return "".join(s.get("plain_text", "") for s in segments)

    def _blocks_to_markdown(self, page_id: str) -> str:
        data = self._get(f"/blocks/{page_id}/children")
        if not data:
            return ""
        lines = []
        for block in data.get("results", []):
            btype = block.get("type", "")
            payload = block.get(btype, {})
            text = self._rich_text(payload.get("rich_text", []))

            if btype == "heading_1":
                lines.append(f"# {text}")
            elif btype == "heading_2":
                lines.append(f"## {text}")
            elif btype == "heading_3":
                lines.append(f"### {text}")
            elif btype == "paragraph":
                lines.append(text)
            elif btype == "bulleted_list_item":
                lines.append(f"- {text}")
            elif btype == "numbered_list_item":
                lines.append(f"1. {text}")
            elif btype == "to_do":
                mark = "x" if payload.get("checked") else " "
                lines.append(f"- [{mark}] {text}")
            elif btype == "quote":
                lines.append(f"> {text}")
            elif btype == "code":
                lang = payload.get("language", "")
                lines.append(f"```{lang}\n{text}\n```")
            elif btype == "divider":
                lines.append("---")
            elif btype == "callout":
                icon = payload.get("icon", {}).get("emoji", "")
                lines.append(f"> {icon} {text}")
            else:
                if text:
                    lines.append(text)
        return "\n\n".join(filter(None, lines))

    def _page_title(self, page: dict) -> str:
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                return self._rich_text(prop.get("title", []))
        return ""

    def _fetch_page(self, page_id: str) -> tuple[str, str, str]:
        """Returns (title, markdown, url)."""
        clean_id = page_id.replace("-", "")
        page = self._get(f"/pages/{clean_id}")
        if not page:
            return "", "", ""
        title = self._page_title(page)
        url = page.get("url", "")
        body = self._blocks_to_markdown(clean_id)
        markdown = f"# {title}\n\n{body}" if title else body
        return title, markdown, url

    def _slug(self, title: str, fallback: str) -> str:
        if title:
            safe = "".join(c if c.isalnum() or c in " _-" else "" for c in title)
            return safe.strip().replace(" ", "_")[:50]
        return fallback[:12]

    def run(self, config: dict, raw_dir: str) -> list[DepositedFile]:
        page_ids = config.get("page_ids", [])
        db_ids = config.get("database_ids", [])
        max_db = min(config.get("max_db_pages", 100), 100)
        raw = Path(raw_dir)
        notion_dir = raw / "notion"
        notion_dir.mkdir(parents=True, exist_ok=True)
        deposited = []

        for pid in page_ids:
            title, content, url = self._fetch_page(pid)
            if not content:
                continue
            path = notion_dir / f"{self._slug(title, pid)}.md"
            path.write_text(content, encoding="utf-8")
            deposited.append(DepositedFile(
                path=str(path.relative_to(raw)),
                content=content,
                source_url=url,
                title=title or pid,
            ))

        for db_id in db_ids:
            clean_id = db_id.replace("-", "")
            data = self._post(f"/databases/{clean_id}/query", {"page_size": max_db})
            if not data:
                continue
            db_dir = notion_dir / f"db_{clean_id[:8]}"
            db_dir.mkdir(exist_ok=True)
            for page in data.get("results", []):
                pid = page["id"]
                title, content, url = self._fetch_page(pid)
                if not content:
                    continue
                path = db_dir / f"{self._slug(title, pid)}.md"
                path.write_text(content, encoding="utf-8")
                deposited.append(DepositedFile(
                    path=str(path.relative_to(raw)),
                    content=content,
                    source_url=url,
                    title=title or pid,
                ))

        print(f"[notion] ✅ {len(deposited)} pages ingested")
        return deposited
