# admin_bot — Example conversation

The admin bot is your personal AI agent — named by you in `config.json → agent.name`.
It has access to all 6 memory layers: your wiki, your daily notes, your decisions,
and everything the automation scripts have done.

Config used in this example:
- `agent.name`: Nova
- `agent.brain_name`: alex
- Projects in wiki: Startup, Freelance

---

## Morning briefing (6:30 AM — auto-triggered)

```
🤖 Nova [6:30 AM]
☀️ Good morning. Open commitments:

• Follow up with David on invoice — since yesterday
• Review pitch deck draft with co-founder — since 2 days ago

System running normally.
```

---

## Asking about commitments

```
👤 Alex [8:00 AM]
What's on my plate right now?
```

```
🤖 Nova [8:00 AM]
Open commitments:

1. Follow up with David on invoice (since yesterday)
2. Review pitch deck draft (since 2 days ago)
3. Set up error monitoring for Startup (since last week)

Want me to mark any of these as done?
```

```
👤 Alex [8:01 AM]
Mark the invoice follow-up as done — sent it this morning.
```

```
🤖 Nova [8:01 AM]
✅ Marked resolved: Follow up with David on invoice.

2 open commitments remaining.
```

---

## Project context query (brain search — Layer 3)

```
👤 Alex [10:30 AM]
Quick recap — what's the current status of the Startup?
```

```
🤖 Nova [10:30 AM]
From your wiki (last updated 3 days ago):

**Startup — current status**
- Stripe integration: shipped this week ✅
- Pitch deck: in progress — co-founder review pending
- Next milestone: seed round outreach, target Q3

From your recent notes:
- Co-founder call yesterday: scope of pitch deck agreed, deck draft due this week
- You have 2 open tasks in Startup topic this week

Anything specific you want to dig into?
```

---

## Temporal query (Layer 3b — daily notes)

```
👤 Alex [Friday 6:00 PM]
What did I actually get done this week?
```

```
🤖 Nova [Friday 6:00 PM]
From your daily notes this week:

**Shipped:**
- Stripe webhook handler (completed Wed)
- Sent freelance invoice to David ($1,200)

**In progress:**
- Pitch deck draft — co-founder review needed
- Error monitoring setup — not started

**Habits:**
- Gym: 3/5 days (Mon, Wed, Thu)
- Meditation: 2/5

Solid week on the Startup side. Pitch deck is the blocker to unblock before EOW.
```

---

## System status query (Layer 6 — action log)

```
👤 Alex [8:00 AM Saturday]
Did the weekly scripts run?
```

```
🤖 Nova [8:00 AM]
Recent system actions (last 24h):

✅ weekly-planning.timer — ran Sat 8:00 AM → created Weekly Review W22 in vault
✅ weekly-digest.timer — ran Sat 9:00 PM → generated intel digest in agent-vault
✅ vault-ingest.timer — ran daily 5:00 AM → 3 new wiki pages indexed (Startup, Freelance)
✅ vault-brain-sync — ran 7:00 AM → 12 chunks updated in ChromaDB

Everything ran cleanly. No errors in the last 48h.
```

---

## Decision capture (Layer 5)

```
👤 Alex [3:00 PM]
I've decided to drop the mobile app for now and focus on the web version only.
```

```
🤖 Nova [3:00 PM]
Got it. I'll remember that.

To confirm: dropping mobile app from Startup scope, focusing web-only.
Any timeline or trigger to revisit this decision?
```

```
👤 Alex [3:01 PM]
Revisit after the seed round closes.
```

```
🤖 Nova [3:01 PM]
✅ Decision saved: Drop mobile app, focus web-only. Revisit after seed round closes.

This will surface in your briefings if mobile comes up again.
```

---

## What's different from a regular LLM

A regular LLM has no memory between conversations.
Nova's answers above come from real sources that accumulate over time:

| Answer came from | Memory layer |
|-----------------|-------------|
| "Stripe shipped this week" | Layer 3b — your daily notes |
| "Pitch deck in progress" | Layer 3 — your wiki (vault-ingest ran yesterday) |
| "Weekly scripts ran" | Layer 6 — action log from the VPS |
| "Open commitments" | Layer 5 — extracted from past conversations |
| "You decided to drop mobile" | Layer 5 — this conversation, saved automatically |
