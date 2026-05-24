---
name: culver-weekly
version: 1.0.0
description: |
  Create or complete the weekly review in Obsidian. Reads the past 7 daily notes,
  summarizes progress on projects and habits, and writes the weekly review file.
allowed-tools:
  - Bash
  - Read
  - Write
---

# /culver-weekly

Generate the weekly review by reading the past 7 daily notes and summarizing progress.

---

## Step 1: Read config and determine week

```bash
python3 -c "
import json, datetime
c = json.load(open('$HOME/.culver/config.json'))
today = datetime.date.today()
week_num = today.isocalendar()[1]
year = today.year
monday = today - datetime.timedelta(days=today.weekday())
sunday = monday + datetime.timedelta(days=6)
print('WEEK=W' + str(week_num))
print('YEAR=' + str(year))
print('MONDAY=' + monday.isoformat())
print('SUNDAY=' + sunday.isoformat())
print('VAULT_PATH=' + c['obsidian']['vault_path'])
print('WEEKLY_DIR=' + c['obsidian']['vault_path'] + '/' + c['obsidian'].get('weekly_reviews_subdir', 'Weekly Reviews'))
print('DAILY_DIR=' + c['obsidian']['vault_path'] + '/' + c['obsidian'].get('daily_notes_subdir', 'Daily Notes'))
"
```

---

## Step 2: Read daily notes from this week

```bash
DAILY_DIR=<from above>
MONDAY=<from above>

echo "=== Daily notes this week ==="
for i in 0 1 2 3 4 5 6; do
  DATE=$(date -d "$MONDAY + $i days" +%Y-%m-%d 2>/dev/null || \
         python3 -c "import datetime; d=datetime.date.fromisoformat('$MONDAY'); print((d + datetime.timedelta(days=$i)).isoformat())")
  FILE="$DAILY_DIR/$DATE.md"
  if [ -f "$FILE" ]; then
    echo "--- $DATE ---"
    cat "$FILE"
    echo ""
  else
    echo "--- $DATE: no note ---"
  fi
done
```

---

## Step 3: Check if weekly review exists

```bash
WEEKLY_DIR=<from above>
WEEK=<from above>
YEAR=<from above>
REVIEW_PATH="$WEEKLY_DIR/$YEAR-$WEEK.md"

if [ -f "$REVIEW_PATH" ]; then
  echo "REVIEW_EXISTS=true"
  cat "$REVIEW_PATH"
else
  echo "REVIEW_EXISTS=false"
fi
```

---

## Step 4: Generate weekly review

Using the daily notes read in Step 2, generate a weekly review with:
- Summary of what was accomplished this week per project
- Habit tracking: which habits were completed and how many days
- Wins and learnings
- Open items / what carries over to next week
- One-sentence focus for next week

Use the template at `~/.claude/skills/culver/_templates/weekly-review.md`.

If the review already exists, read it first and only fill in the sections that are empty. Do not overwrite existing content.

Write to `$REVIEW_PATH`.

---

## Step 5: Confirm

```bash
ls -la "$REVIEW_PATH" && echo "✅ Weekly review ready: $YEAR-$WEEK"
```
