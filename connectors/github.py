"""
connectors/github.py — Ingests GitHub repos: READMEs, open issues, and open PRs.

Config section in config.json:
    "connectors": {
        "github": {
            "repos": ["owner/repo1", "owner/repo2"],
            "include": ["readme", "issues", "prs"],
            "max_items": 50
        }
    }

Env: GITHUB_PAT (already required by the admin bot — no new credential needed)
"""

import base64
import os
from pathlib import Path

import requests

from connectors.base import BaseConnector, DepositedFile

API = "https://api.github.com"


class GitHubConnector(BaseConnector):

    def name(self) -> str:
        return "github"

    def validate_config(self, config: dict) -> bool:
        if not os.environ.get("GITHUB_PAT"):
            print("[github] ERROR: GITHUB_PAT not set")
            return False
        if not config.get("repos"):
            print("[github] WARNING: no repos configured — nothing to ingest")
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['GITHUB_PAT']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, url: str, params: dict = None):
        try:
            r = requests.get(url, headers=self._headers(), params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[github] ERROR {url}: {e}")
            return None

    def run(self, config: dict, raw_dir: str) -> list[DepositedFile]:
        repos = config.get("repos", [])
        include = config.get("include", ["readme", "issues", "prs"])
        max_items = min(config.get("max_items", 50), 100)
        raw = Path(raw_dir)
        deposited = []

        for repo in repos:
            repo_dir = raw / "github" / repo.replace("/", "__")
            repo_dir.mkdir(parents=True, exist_ok=True)

            if "readme" in include:
                deposited += self._ingest_readme(repo, repo_dir, raw)
            if "issues" in include:
                deposited += self._ingest_issues(repo, repo_dir, raw, max_items)
            if "prs" in include:
                deposited += self._ingest_prs(repo, repo_dir, raw, max_items)

        print(f"[github] ✅ {len(deposited)} items from {len(repos)} repos")
        return deposited

    def _ingest_readme(self, repo: str, dest: Path, raw: Path) -> list[DepositedFile]:
        data = self._get(f"{API}/repos/{repo}/readme")
        if not data:
            return []
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
        except Exception:
            return []
        path = dest / "README.md"
        path.write_text(content, encoding="utf-8")
        return [DepositedFile(
            path=str(path.relative_to(raw)),
            content=content,
            source_url=data.get("html_url", ""),
            title=f"{repo} — README",
        )]

    def _ingest_issues(self, repo: str, dest: Path, raw: Path, max_items: int) -> list[DepositedFile]:
        data = self._get(f"{API}/repos/{repo}/issues", {"state": "open", "per_page": max_items})
        if not data:
            return []
        deposited = []
        for issue in data:
            if "pull_request" in issue:
                continue
            num = issue["number"]
            title = issue["title"]
            body = issue.get("body") or ""
            labels = ", ".join(l["name"] for l in issue.get("labels", []))
            content = f"# Issue #{num}: {title}\n\n**Labels:** {labels}\n\n{body}"
            path = dest / f"issue_{num}.md"
            path.write_text(content, encoding="utf-8")
            deposited.append(DepositedFile(
                path=str(path.relative_to(raw)),
                content=content,
                source_url=issue.get("html_url", ""),
                title=f"{repo} Issue #{num}: {title}",
            ))
        return deposited

    def _ingest_prs(self, repo: str, dest: Path, raw: Path, max_items: int) -> list[DepositedFile]:
        data = self._get(f"{API}/repos/{repo}/pulls", {"state": "open", "per_page": max_items})
        if not data:
            return []
        deposited = []
        for pr in data:
            num = pr["number"]
            title = pr["title"]
            body = pr.get("body") or ""
            content = f"# PR #{num}: {title}\n\n{body}"
            path = dest / f"pr_{num}.md"
            path.write_text(content, encoding="utf-8")
            deposited.append(DepositedFile(
                path=str(path.relative_to(raw)),
                content=content,
                source_url=pr.get("html_url", ""),
                title=f"{repo} PR #{num}: {title}",
            ))
        return deposited
