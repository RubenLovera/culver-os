# Feeding Your Brain

This is the most important step after installation. CulverOS is only as smart as the information you give it. This guide shows you how to go from a fresh install to a system that knows your projects, your history, and your thinking — with Obsidian's graph view as the visual proof it's working.

---

## How the pipeline works

Every source feeds into one place: the `raw/` folder in your agent vault.

```
Any source
    ↓
raw/{source}/YYYY-MM-DD-title.md
    ↓
vault-ingest.py (runs daily at 5:00 AM)
    → reads raw/ files not yet in log.md
    → calls LLM → generates structured wiki pages in wiki/
    → updates MASTER_INDEX.md + log.md
    ↓
vault-brain-sync.py (runs daily at 7:00 AM)
    → detects changed wiki/ pages
    → re-indexes into ChromaDB
    ↓
Your admin bot knows what you wrote.
Obsidian shows the connections visually.
```

The rule: **anything you put in `raw/` gets processed and connected**. You don't need to format it perfectly — the LLM reads it and generates structured wiki pages with wikilinks to related topics.

---

## Method 1 — Write in Obsidian (the main loop)

This is the highest-leverage habit. Every note you write in Obsidian flows into CulverOS through the `obsidian_sync` connector, which runs automatically.

**What to write:**
- Daily notes — your `diario_bot` creates these automatically each morning. Add your thoughts, wins, tasks during the day.
- Project notes — create a note per project. Update it when something changes.
- Weekly reviews — your bot creates these every Sunday. Fill them in.
- Free notes — ideas, reflections, anything you want the system to know

**Where it goes:**
```
You write in Obsidian App
    → Obsidian Git plugin auto-syncs to GitHub (every 1 min)
    → VPS pulls from GitHub (every 2h)
    → obsidian_sync connector copies to raw/personal_vault/
    → vault-ingest processes it tomorrow at 5 AM
```

**The compounding effect:** as you write daily notes consistently, vault-ingest connects them. A note about a decision links to the project. A project links to a person. A person links to a company. After 2–3 weeks, your wiki has a web of connections.

---

## Method 2 — Obsidian Web Clipper (for the web)

[Obsidian Web Clipper](https://obsidian.md/clipper) is a browser extension (Chrome, Firefox, Safari) that saves any web page directly to your vault as a markdown file.

**Install:**
1. Go to [obsidian.md/clipper](https://obsidian.md/clipper) → install for your browser
2. Open the extension settings → set the save folder to `raw/articles/`
3. Configure the template to include frontmatter (title, source URL, date)

**Recommended template:**
```markdown
---
title: "{{title}}"
source: "{{url}}"
date: "{{date}}"
connector: "web-clipper"
---

{{content}}
```

**What to clip:**
- Articles about your industry or projects
- Competitor analysis
- Research papers
- Interesting blog posts, newsletters
- Documentation you want your agent to know

Once clipped, the file lands in `raw/articles/` and vault-ingest picks it up the next morning.

---

## Method 3 — Manual drops into raw/

For any source that doesn't have a connector yet (Notion exports, Fathom calls, meeting notes, email threads), you can drop markdown files directly into `raw/`.

**File naming convention:**
```
raw/{source}/YYYY-MM-DD-descriptive-title.md
```

Examples:
```
raw/calls/2026-05-20-investor-call-sequoia.md
raw/notion-exports/2026-05-15-product-roadmap.md
raw/emails/2026-05-18-partnership-reply-acme.md
raw/startup-updates/2026-05-20-q2-status.md
```

**Minimum frontmatter:**
```markdown
---
title: "Descriptive title"
source: "notion-export / fathom / email / manual"
date: "YYYY-MM-DD"
---

Your content here...
```

**How to get the file into the vault:**
1. Write or paste content into a `.md` file on your Mac
2. Save it under `~/Documents/Obsidian Vault/raw/{source}/` (or wherever your vault is)
3. Obsidian Git syncs it to GitHub → VPS picks it up → vault-ingest processes it

> Tip: keep a folder `~/Desktop/brain-inbox/` and drop files there during the day. Before bed, move them to the right `raw/` subfolder in Obsidian.

---

## Method 4 — Automated connectors

These run without any manual action once configured.

### obsidian_sync (built-in ✅)
Copies notes from your personal Obsidian vault into `raw/personal_vault/`. Configured in `config.json` under `connectors.obsidian_sync`. Runs with the `obsidian-brain-sync` timer every 2h.

### vault-ingest web research (built-in ✅)
Every morning at 5 AM, vault-ingest runs a web research pass on your configured topics (pulled from your `config.json → projects`). Results land in `raw/market_news/`. No setup needed — it starts running the day after you deploy.

### Coming in v1+ (architecture ready, not yet implemented)

| Connector | Source | What it captures |
|-----------|--------|-----------------|
| `notion` | Notion databases & pages | Project docs, meeting notes, wikis |
| `granola` | Granola meeting notes | Auto-transcribed meetings with action items |
| `fathom` | Fathom call recordings | Sales calls, interviews, 1:1s |
| `gmail` | Gmail threads | Key email conversations |
| `github` | GitHub repos | Issues, PRs, READMEs of your projects |
| `gcal` | Google Calendar | Meeting context, recurring patterns |
| `readwise` | Readwise highlights | Kindle, articles, Twitter bookmarks |

To build a custom connector, subclass `BaseConnector` from `connectors/base.py`. See `connectors/README.md`.

---

## All sources — reference table

| Source | Method | Frequency | Effort |
|--------|--------|-----------|--------|
| Obsidian notes | Auto (obsidian_sync) | Every 2h | None after setup |
| Web articles | Obsidian Web Clipper | On demand | 1 click per article |
| Web research | Auto (vault-ingest) | Daily 5 AM | None after setup |
| Meeting notes (Granola) | Manual drop → raw/calls/ | After each meeting | ~2 min |
| Call transcripts (Fathom) | Manual drop → raw/calls/ | After each call | ~2 min |
| Notion exports | Manual drop → raw/notion-exports/ | Weekly | ~5 min |
| Email threads | Copy-paste → raw/emails/ | On demand | ~1 min |
| GitHub READMEs | Manual drop → raw/github/ | On demand | ~1 min |
| Voice memos | Transcribe → raw/notes/ | On demand | ~2 min |
| Books/highlights | Readwise export → raw/books/ | Monthly | ~5 min |
| YouTube transcripts | Copy transcript → raw/articles/ | On demand | ~2 min |
| Twitter threads | Web Clipper or copy → raw/articles/ | On demand | ~1 min |
| Startup updates | Write directly → raw/startup-updates/ | Weekly | ~10 min |

---

## The cold start (first week)

The system doesn't know anything about you yet. Here's the fastest way to fix that.

**Day 1 — seed your projects (30 min)**

For each active project, create a note in Obsidian:

```markdown
---
title: "Project Name — Overview"
source: "manual"
date: "today"
---

## What it is
[2–3 sentences]

## Current status
[Where things are today]

## Key people
- [Name] — [role]

## History
[Key decisions, what you tried, what worked]

## Open questions
- [Question 1]
- [Question 2]
```

Save these in `raw/startup-updates/`. Tomorrow morning, vault-ingest turns them into wiki pages with cross-links.

**Day 2–7 — write daily**

Open your daily note each morning (diario_bot sends it at 5:45 AM). Write in it during the day. The system learns your rhythm, your vocabulary, your priorities.

**Week 2 — start clipping**

Install Obsidian Web Clipper. Every article you read that's relevant to your work: clip it. Over 2–3 weeks you accumulate a library of processed knowledge your agent can query.

---

## Seeing it in Obsidian — the graph view

Once vault-ingest has processed your first batch of content (next morning after day 1), open Obsidian and switch to Graph View.

**How to open it:**

1. Open Obsidian
2. Press `Cmd+Shift+G` (Mac) or `Ctrl+Shift+G` (Windows)
3. Or: click the graph icon in the left sidebar

**What you'll see:**

Each dot is a note. Each line is a wikilink connecting two notes. As vault-ingest runs daily, the graph grows — your projects connect to people, people connect to companies, companies connect to market context.

After a week of writing daily notes and feeding raw/ consistently, you'll see a constellation. After a month, it's a dense web of your knowledge — and your admin bot can query any part of it.

**Tips to make the graph better:**
- In Graph View settings, enable **Groups** — color your nodes by folder (wiki/ in one color, daily notes in another)
- Enable **Filters** — hide daily notes to see only your wiki structure
- Zoom into clusters to see which topics are most connected

The graph is the visual proof that your second brain is working.

---

## Checklist — first 24 hours

- [ ] Write project overviews for each active project → save to `raw/startup-updates/`
- [ ] Install [Obsidian Web Clipper](https://obsidian.md/clipper) → configure save folder to `raw/articles/`
- [ ] Write your first daily note (or wait for diario_bot to send it at 5:45 AM tomorrow)
- [ ] Wait for vault-ingest to run (5:00 AM next day) — check `raw/market_news/` for the first auto-generated brief
- [ ] Open Obsidian Graph View (`Cmd+Shift+G`) — see your first connections
