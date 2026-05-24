# CulverOS

![CulverOS](assets/culver-os-logo.png)

**A Personal AI Operating System you can install in one command.**

CulverOS gives you a 24/7 personal AI agent running on your own VPS — with a semantic brain that knows your projects, your notes, and your commitments. Installed entirely through a conversation in Claude Code.

---

## What you get

- **Admin agent** — your personal AI, named by you, running 24/7 on Telegram
- **CulverBrain v3.0** — 6 memory layers: semantic knowledge base, interaction memory, action audit log
- **LLM-wiki** — automatic pipeline that converts your notes and sources into structured knowledge (inspired by [Karpathy's LLM-wiki](https://gist.github.com/RubenLovera/bdd39168ebf57ba3a116c63997d4abd0))
- **Two-vault architecture** — personal vault (your daily notes) + agent vault (AI-compiled wiki)
- **15 automated timers** — daily notes, vault ingestion, weekly planning, brain sync
- **Full ownership** — your VPS, your GitHub repos, your data

---

## Install

Open Claude Code and paste this:

```
Install my Personal AI OS: run curl -fsSL https://raw.githubusercontent.com/RubenLovera/culver-os/main/install.sh | bash then immediately read and follow ~/.claude/skills/culver/culver-onboarding/SKILL.md from start to finish — check prerequisites, ask me the setup questions, generate my config, create my GitHub repos, and deploy my VPS bots.
```

That's it. Claude Code runs the installer, asks you 10 questions, and sets up everything end-to-end in about 10 minutes.

---

## Prerequisites

- [Claude Code](https://claude.ai/code) installed (`npm install -g @anthropic-ai/claude-code`)
- A GitHub account with a Personal Access Token (repo + read:org scopes)
- A VPS running Ubuntu 24.04 — [Hostinger](https://hostinger.com) works well (~$4/mo)
- A Telegram account (for the bot)
- An LLM API key for the ingestion pipeline — Gemini (free at [aistudio.google.com](https://aistudio.google.com)), Claude, or OpenAI
- [Obsidian](https://obsidian.md) Desktop (recommended, for notes sync)

The install script also installs [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) automatically — 5 skills that make Claude Code an expert at working with Obsidian vaults:

| Skill | What it does |
|-------|-------------|
| `obsidian-markdown` | Create and edit Obsidian Flavored Markdown — wikilinks, callouts, embeds, properties |
| `obsidian-bases` | Create and edit Obsidian Bases (.base) — views, filters, formulas, summaries |
| `json-canvas` | Create and edit JSON Canvas files (.canvas) — visual nodes, edges, connections |
| `obsidian-cli` | Interact with vaults via the Obsidian CLI — plugin/theme dev, vault operations |
| `defuddle` | Extract clean markdown from web pages — removes clutter to save tokens |

To install them separately: `npx skills add https://github.com/kepano/obsidian-skills`

---

## Manual setup walkthrough

This is what you'll see in your terminal when setting up CulverOS for the first time. No credentials needed until you deploy to VPS.

### 0. Install Obsidian skills

```bash
npx skills add https://github.com/kepano/obsidian-skills
```

Output:
```
✅ obsidian-markdown installed
✅ obsidian-bases installed
✅ json-canvas installed
✅ obsidian-cli installed
✅ defuddle installed
```

These skills are also installed automatically by `install.sh`. Once installed, Claude Code knows how to create wikilinks, Bases, Canvases, and interact with Obsidian vaults — the same capability used by the vault-ingest pipeline.

### 1. Clone and configure

```bash
git clone https://github.com/RubenLovera/culver-os.git
cd culver-os
cp config.template.json config.json
```

Edit `config.json` — replace all `{{PLACEHOLDER}}` values with your own. The required fields are: your name, timezone, Telegram bot tokens, GitHub PAT, and LLM API key. The rest can be filled in later.

### 2. Generate your .env files

```bash
python3 scripts/generate_env.py config.json deploy/output/env/
```

Output:
```
✅ Generated deploy/output/env/.env.admin
✅ Generated deploy/output/env/.env.diario
```

Two files are generated — one for the admin bot, one for the daily notes bot. Each contains the env vars that bot needs.

### 3. Generate systemd timers

```bash
python3 scripts/generate_timers.py config.json
```

Output:
```
  ℹ️  Local mode — output: deploy/output/systemd

  ✅ Generated log-rotate.service
  ✅ Generated log-rotate.timer
  ✅ Generated daily-note.service
  ✅ Generated daily-note.timer
  ✅ Generated vault-ingest.service
  ✅ Generated vault-ingest.timer
  ... (15 timers total)

✅ 15 timers generated. Copy to /etc/systemd/system/ on your VPS.
   Files in: deploy/output/systemd
```

This generates 30 files (service + timer unit for each automation) in `deploy/output/systemd/`. They are parametrized with your `config.json` values — vault paths, schedules, and agent names are all substituted.

### 4. Verify locally

```bash
python3 tests/smoke_test.py
```

Output:
```
CulverOS Framework — Smoke Test
========================================
(no credentials required)

[OK]   import tools.paperclip
[OK]   import tools.obsidian
[OK]   import tools.daily_note
...
[OK]   generate_timers.py TIMERS = 15
[OK]   systemd templates count = 31

74/74 tests passed  (3 skipped — VPS-only)
```

The 3 skipped tests (`chromadb`) are VPS-only — they pass on the server once ChromaDB is running.

### 5. Deploy to VPS

```bash
# Copy generated files to your VPS
scp deploy/output/env/.env.admin root@YOUR_VPS_IP:/root/culver-os/
scp deploy/output/env/.env.diario root@YOUR_VPS_IP:/root/culver-os/
scp deploy/output/systemd/* root@YOUR_VPS_IP:/etc/systemd/system/

# On the VPS — clone the repo, install deps, enable timers
ssh root@YOUR_VPS_IP
cd /root && git clone https://github.com/RubenLovera/culver-os.git
cd culver-os && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
systemctl daemon-reload
systemctl enable --now admin-bot
for f in /etc/systemd/system/*.timer; do systemctl enable --now "$(basename $f)"; done
```

### What's next after installation

Once your VPS is running and your bots are live, the next step is feeding the system with your knowledge.

→ **[Feeding Your Brain — complete guide](docs/feeding-your-brain.md)**

This guide covers: writing in Obsidian, Obsidian Web Clipper, manual drops into `raw/`, automated connectors, a cold-start checklist, and how to open the graph view to see your second brain visually.

---

## How it works

```
curl | bash
  └── installs ~/.claude/skills/culver/ on your Mac

/culver-onboarding (Claude Code)
  ├── asks 10 questions
  ├── generates ~/.culver/config.json
  ├── creates your private GitHub repos
  ├── parametrizes all scripts + agents with your config
  └── calls /culver-bootstrap-vps

/culver-bootstrap-vps
  ├── installs docker + python on your VPS via SSH
  ├── starts ChromaDB + your admin bot (docker-compose)
  └── enables all 15 systemd timers
```

---

## CulverBrain — 6 memory layers

| Layer | Type | What it stores |
|-------|------|----------------|
| 1 | In-context | CLAUDE.md + agent identity |
| 2 | Procedural | MASTER_INDEX, status reports, user profile |
| 3 | Semantic | ChromaDB `{brain}_brain` — knowledge base from your wiki |
| 3b | Temporal | Daily notes filesystem — last 7 days |
| 4 | Episodic | log.md, session reports |
| 5 | Interactional | ChromaDB `{brain}_interactions` — your decisions & commitments |
| 6 | Actional | JSONL + ChromaDB `{brain}_actions` — everything the bots did |

---

## LLM-Wiki — How your agent learns about you

The LLM-wiki is the intelligence layer that makes your agent useful from day one.

```
You write in Obsidian (or anywhere)
     ↓
obsidian_sync connector copies notes to raw/
     ↓
vault-ingest.py (12:00 UTC daily):
  → reads raw/ files not yet in log.md
  → calls LLM → generates structured wiki pages in wiki/
  → updates MASTER_INDEX.md + log.md
  → pushes to GitHub (agent vault)
     ↓
vault-brain-sync.py (14:00 UTC daily):
  → detects changed wiki/ files via git diff
  → re-indexes into ChromaDB
     ↓
Your admin bot now knows what you wrote
```

**The difference from simple RAG:** your wiki *composes and accumulates*. RAG rediscovers from scratch each time. The wiki compounds — each entry links to related pages, and the agent can query it semantically.

**LLM-agnostic:** works with Gemini, Claude, or OpenAI. Configure once in `config.json`.

**Connectors extend what gets ingested:** Obsidian sync is pre-built. Notion, Gmail, GitHub, Granola → v1+. Build your own following `connectors/README.md`.

---

## Skills

| Skill | What it does |
|-------|-------------|
| `/culver-onboarding` | Full setup wizard |
| `/culver-bootstrap-vps` | Provision VPS + deploy runtime |
| `/culver-bootstrap-local` | Install local prerequisites |
| `/culver-healthcheck` | Check all services + timers |
| `/culver-daily` | Create today's daily note |
| `/culver-weekly` | Generate weekly review |
| `/culver-ingest` | Manually trigger vault ingestion |
| `/culver-add-connector` | Enable or build a data connector |
| `/culver-brain-sync` | Re-index vaults into ChromaDB |
| `/culver-connect-agent` | Connect your own bot to the brain |
| `/culver-uninstall` | Remove CulverOS from this machine |

---

## Architecture

```
Your Mac
├── Claude Code
│   └── ~/.claude/skills/culver/   ← skills (installed by this repo)
├── ~/.culver/config.json          ← your config (generated by onboarding)
└── ~/culver-os-{you}/             ← your private instance (GitHub repo)

VPS (24/7)
└── /root/culver-os/
    ├── agents/admin_bot.py        ← your admin agent (Telegram)
    ├── tools/brain.py             ← ChromaDB client
    ├── tools/memory.py            ← Layers 5 + 6
    ├── scripts/                   ← 15 automation scripts
    └── docker-compose.yml         ← ChromaDB + admin bot

GitHub (private)
├── {you}/culver-os-{you}          ← your parametrized instance
├── {you}/personal-vault           ← your daily notes (synced by Obsidian Git)
└── {you}/agent-vault              ← AI-compiled wiki + raw sources
```

---

## Adding your own agents

Any Python bot on the same VPS can connect to your brain in 3 lines:

```python
import sys
sys.path.insert(0, "/root/culver-os")

from tools.brain import query_filtered          # semantic search
from tools.memory import record_interaction     # Layer 5
from tools.memory import record_action          # Layer 6
```

Run `/culver-connect-agent` for a guided walkthrough.

---

## License

MIT