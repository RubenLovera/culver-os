# CulverOS Connectors

Connectors read data from external sources and deposit files into the agent vault's `raw/` directory, making them available for `vault-ingest.py` to process into wiki pages.

## Pre-built connectors

| Connector | Source | Status |
|-----------|--------|--------|
| `obsidian_sync` | Personal Obsidian vault | ✅ MVP |
| `notion` | Notion pages/databases | v1+ |
| `gmail` | Gmail threads | v1+ |
| `github` | Issues, PRs, READMEs | v1+ |
| `granola` | Meeting notes | v1+ |
| `fathom` | Call transcripts | v1+ |

## Enabling a connector

In your `config.json`:

```json
"connectors": {
  "enabled": ["obsidian_sync"],
  "obsidian_sync": {
    "sync_folders": ["Daily Notes", "Weekly Reviews"],
    "max_days": 30
  }
}
```

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
