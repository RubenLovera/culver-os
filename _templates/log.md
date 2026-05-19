# Agent Vault — Operations Log

Append-only chronological record of all vault operations.

**Format:**
- `## [YYYY-MM-DD] ingest | filename` — file processed by vault-ingest.py
- `## [YYYY-MM-DD] query | question` — query archived as wiki page
- `## [YYYY-MM-DD] lint | N issues` — lint audit run

**Rules:**
- Never overwrite existing entries
- Always append at the bottom
- vault-ingest.py writes to this file automatically

---

## [{{DATE}}] init | vault initialized

