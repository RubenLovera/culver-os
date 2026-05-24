---
name: culver-daily
version: 1.0.0
description: |
  Create today's daily note in Obsidian. Reads habits and sections from
  ~/.culver/config.json and generates a note using the daily-note template.
  Can also be triggered by the daily-note.timer on the VPS automatically.
allowed-tools:
  - Bash
  - Read
  - Write
---

# /culver-daily

Create today's daily note in Obsidian using the template configured during onboarding.

---

## Step 1: Read config

```bash
python3 -c "
import json, datetime
c = json.load(open('$HOME/.culver/config.json'))
today = datetime.date.today().isoformat()
print('TODAY=' + today)
print('USER_NAME=' + c['user']['name'])
print('VAULT_PATH=' + c['obsidian']['vault_path'])
print('DAILY_DIR=' + c['obsidian']['vault_path'] + '/' + c['obsidian'].get('daily_notes_subdir', 'Daily Notes'))
habits = c.get('daily_note', {}).get('habits', [])
print('HABITS=' + '|'.join(habits))
"
```

---

## Step 2: Check if today's note exists

```bash
DAILY_DIR=<from above>
TODAY=<from above>
NOTE_PATH="$DAILY_DIR/$TODAY.md"

if [ -f "$NOTE_PATH" ]; then
  echo "NOTE_EXISTS=true"
  cat "$NOTE_PATH"
else
  echo "NOTE_EXISTS=false"
fi
```

If the note already exists, show it to the user and ask if they want to open it or add something to it. Do not overwrite.

---

## Step 3: Generate and write the note

If no note exists, generate it from the template at `~/.claude/skills/culver/_templates/daily-note.md`, substituting:
- `{{DATE}}` → today's date (YYYY-MM-DD)
- `{{USER_NAME}}` → user's name
- `{{HABITS}}` → list of habits as checkboxes
- `{{PROJECTS}}` → user's project names as section headers
- `{{SECTIONS}}` → any custom sections from config

Write the file to `$DAILY_DIR/$TODAY.md`.

---

## Step 4: Confirm

```bash
ls -la "$DAILY_DIR/$TODAY.md" && echo "✅ Daily note created: $TODAY"
```

Tell the user the note was created and is ready in Obsidian. If they have the Obsidian Git plugin set to auto-pull, it will sync within 2 minutes.
