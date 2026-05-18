---
name: culver-uninstall
version: 1.0.0
description: |
  Remove CulverOS skills and local config from this machine.
  Does NOT touch the VPS — you must clean that up manually.
  Use when you want a clean reinstall or to remove CulverOS entirely.
allowed-tools:
  - Bash
  - AskUserQuestion
---

# /culver-uninstall

Remove CulverOS from this machine. This removes the skills and local config.
The VPS keeps running — you control that separately.

---

## Step 1: Confirm

Ask the user to confirm before removing anything:

"This will remove:
- `~/.claude/skills/culver/` (all skills)
- `~/.culver/config.json` (your local config)

It will NOT touch:
- Your VPS (bot keeps running until you stop it manually)
- Your GitHub repos (agent-vault, culver-os-{username})
- Your Obsidian vault

Are you sure?"

Do not proceed without explicit confirmation.

---

## Step 2: Remove skills and config

```bash
echo "Removing CulverOS skills..."
rm -rf "$HOME/.claude/skills/culver/"
echo "✅ Skills removed"

echo "Removing local config..."
rm -f "$HOME/.culver/config.json"
rmdir "$HOME/.culver" 2>/dev/null || true
echo "✅ Config removed"
```

---

## Step 3: VPS cleanup instructions

Print manual cleanup steps for the VPS:

```
To stop CulverOS on your VPS, SSH in and run:

  cd /root/culver-os
  docker compose down

To remove everything from the VPS:

  docker compose down -v       # stops containers + removes volumes
  rm -rf /root/culver-os/      # removes all files

To disable systemd timers:

  systemctl disable --now daily-note.timer vault-ingest.timer vault-health.timer \
    obsidian-brain-sync.timer status-operativo-wed.timer status-operativo-sun.timer \
    weekly-planning.timer weekly-fill.timer weekly-digest.timer perfil-identidad.timer \
    monthly-planning.timer log-rotate.timer
```

---

## Step 4: Reinstall instructions

```
To reinstall CulverOS fresh:

  curl -fsSL https://raw.githubusercontent.com/RubenLovera/culver-os/main/install.sh | bash

Then run /culver-onboarding in Claude Code.
```
