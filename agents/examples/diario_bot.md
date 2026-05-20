# diario_bot — Example conversation

Diario is your daily notes agent. It owns your Obsidian daily note and
checks in with you throughout the day. All saves go to your vault via GitHub.

Config used in this example:
- `user.name`: Alex
- `daily_note.ventures`: ["Startup", "Freelance"]
- `daily_note.habits`: ["Gym", "Meditation", "Finances"]

---

## Morning kickoff (5:45 AM — auto-triggered)

```
🤖 Diario [5:45 AM]
☀️ Good morning, Alex.

"The Lord is my shepherd; I shall not want."

• Carry forward from yesterday: close Stripe integration (Startup)

How did you wake up today? What's your intention for the day?
```

```
👤 Alex [5:48 AM]
Woke up at 5:30, slept well. Today I want to close the Stripe integration
and send the freelance invoice to the client.
```

```
🤖 Diario [5:48 AM]
✅ Morning feeling + intention saved.

Got it — Stripe close and invoice out. Top 3 priorities for today?
```

```
👤 Alex [5:49 AM]
1. Finish Stripe webhook handler
2. Send invoice to David
3. Gym after work
```

```
🤖 Diario [5:49 AM]
✅ Top 3 saved.

Stripe, invoice, gym. Focused day. Good luck.
```

---

## Midday capture (2:00 PM — auto-triggered if not covered)

```
🤖 Diario [2:00 PM]
How's the day going? Anything completed or to capture?
```

```
👤 Alex [2:04 PM]
Finished the webhook handler. Waiting on David to confirm the invoice amount.
Also had a quick call with the Startup co-founder about the pitch deck.
```

```
🤖 Diario [2:04 PM]
✅ Task saved: Startup — [x] Finish Stripe webhook handler
✅ Task saved: Freelance — [ ] Confirm invoice amount with David (pending)
✅ Note saved: Call with co-founder re: pitch deck

Good progress on Stripe. What's the invoice ballpark — want to capture it in Finances?
```

```
👤 Alex [2:05 AM]
Yeah, $1,200 USD for the month.
```

```
🤖 Diario [2:05 PM]
✅ Income saved: $1,200 USD — Freelance monthly invoice (Freelance)
```

---

## Ad-hoc during the day

```
👤 Alex [4:30 PM]
Just hit gym, 45 min. Crushed it.
```

```
🤖 Diario [4:30 PM]
✅ Habit saved: Gym ✓

Nice. Evening review tonight?
```

---

## Evening review (9:00 PM — auto-triggered)

```
🤖 Diario [9:00 PM]
🌙 Evening Review

You've got gym checked. Still open: wins, what you learned, energy.
What went well today?
```

```
👤 Alex [9:05 PM]
Shipped the Stripe integration. Finally. Took 3 days but it's clean.
```

```
🤖 Diario [9:05 PM]
✅ Wins saved.

What did you learn today — anything from the webhook work or the co-founder call?
```

```
👤 Alex [9:06 PM]
Learned that Stripe signature verification needs the raw body, not parsed JSON.
Wasted 2 hours on that.
```

```
🤖 Diario [9:07 PM]
✅ Lesson saved.

Energy today, 1–10?
```

```
👤 Alex [9:07 PM]
7
```

```
🤖 Diario [9:07 PM]
✅ Energy: 7/10 saved.

Day is complete. Good work shipping Stripe. See you tomorrow at 5:45.
```

---

## What got saved to your vault

By end of day, your daily note has:

```markdown
## Morning
- ¿Cómo amaneciste? Slept well, up at 5:30
- Intención del día: Close Stripe integration + send freelance invoice

## Top 3
1. Finish Stripe webhook handler
2. Send invoice to David
3. Gym after work

## Startup
- [x] Finish Stripe webhook handler
- [ ] Pitch deck follow-up with co-founder

## Freelance
- [ ] Confirm invoice amount with David

## Finanzas del Día
- 💰 Income: $1,200 USD — Freelance monthly invoice

## 🌙 Evening Review
- ¿Qué salió bien hoy? Shipped the Stripe integration. Finally.
- ¿Qué aprendí hoy? Stripe signature verification needs raw body, not parsed JSON.
- Energía del día (1-10): 7/10

## Hábitos
- [x] Gym
```
