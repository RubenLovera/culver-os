# CulverOS Connectors

Connectors read data from external sources and deposit files into the agent vault's `raw/` directory, making them available for `vault-ingest.py` to process into wiki pages.

## Pre-built connectors

| Connector | Source | Requires | Status |
|-----------|--------|----------|--------|
| `obsidian_sync` | Personal Obsidian vault | `PERSONAL_VAULT_PATH` | ✅ |
| `github` | Issues, PRs, READMEs | `GITHUB_PAT` (already in config) | ✅ |
| `notion` | Notion pages/databases | `NOTION_API_KEY` | ✅ |
| `granola` | Meeting transcripts (export folder) | local export dir | ✅ |
| `gmail` | Gmail threads | `GMAIL_*` credentials | planned |
| `fathom` | Call transcripts | `FATHOM_API_KEY` | planned |

## Enabling a connector

Add the connector name to `connectors.enabled` in your `config.json`:

```json
"connectors": {
  "enabled": ["obsidian_sync", "github"],
  "obsidian_sync": {
    "sync_folders": ["Daily Notes", "Weekly Reviews"],
    "max_days": 30
  },
  "github": {
    "repos": ["myuser/myrepo"],
    "include": ["readme", "issues", "prs"],
    "max_items": 50
  },
  "notion": {
    "page_ids": ["your-page-id"],
    "database_ids": [],
    "max_db_pages": 100
  },
  "granola": {
    "export_dir": "/path/to/granola-exports",
    "max_days": 30
  }
}
```

**Notion setup:** create an integration at https://www.notion.so/my-integrations, copy the API key to `NOTION_API_KEY` in your `.env.admin`, and share each page/database with the integration.

**Granola setup:** Granola runs on Mac, not on the VPS. Populate `export_dir` by either: (a) setting Granola to export to a folder that syncs to your VPS via git, or (b) running `tools/export_granola.py` locally on your Mac.

## Building a connector

1. Create `connectors/{your_connector}.py`
2. Subclass `BaseConnector` from `connectors/base.py`
3. Implement the three required methods:

```python
from connectors.base import BaseConnector, DepositedFile

class MyConnector(BaseConnector):

    def name(self) -> str:
        return "my_connector"

    def validate_config(self, config: dict) -> bool:
        # Check that required config keys and env vars are present
        return True

    def run(self, config: dict, raw_dir: str) -> list[DepositedFile]:
        # 1. Read from external source
        # 2. Write markdown files to raw_dir/
        # 3. Return list of DepositedFile objects
        deposited = []
        # ...
        return deposited
```

4. Enable it in `config.json` under `connectors.enabled`

## Output format

Each file deposited in `raw/` should be a Markdown file with optional frontmatter:

```markdown
---
title: "Source title"
source: "https://original-url-or-identifier"
date: "YYYY-MM-DD"
connector: "my_connector"
---

Content here...
```

`vault-ingest.py` uses this frontmatter when generating wiki pages.

## File naming

Use descriptive, date-prefixed filenames to avoid collisions:

```
raw/my_connector/2026-05-18-meeting-title.md
raw/my_connector/2026-05-18-article-slug.md
```

## Testing your connector

```bash
cd /root/culver-os
source venv/bin/activate
python3 -c "
from connectors.my_connector import MyConnector
c = MyConnector()
print(c.validate_config({}))
files = c.run({}, '/tmp/test-raw')
print(f'Deposited {len(files)} files')
"
```
