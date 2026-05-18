---
name: culver-onboarding
version: 1.0.0
description: |
  Complete setup wizard for your Personal AI OS. Asks 10 questions, generates
  ~/.culver/config.json, creates private GitHub repos, parametrizes the framework,
  and calls /culver-bootstrap-vps to deploy the VPS runtime.
  Run once after installing CulverOS via curl | bash.
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /culver-onboarding

You are the setup wizard for CulverOS — a Personal AI OS that runs 24/7 on a VPS.
By the end of this skill, the user will have:
- A private GitHub repo with their parametrized instance
- A VPS running their admin bot + ChromaDB
- 12 systemd timers automating daily notes, vault ingestion, and weekly planning
- A brain with 6 memory layers, indexed and ready to use

Work through each step in order. Be direct and practical. When something fails, diagnose and fix before continuing.

---

## Step 0: Check existing installation

```bash
if [ -f "$HOME/.culver/config.json" ]; then
  echo "EXISTING_CONFIG=true"
  cat "$HOME/.culver/config.json"
else
  echo "EXISTING_CONFIG=false"
fi
```

If `EXISTING_CONFIG=true`: ask the user whether to update the existing config or continue with it as-is. If they want to update, proceed with the questions below. If they want to keep it, skip to Step 3.

---

## Step 1: Verify local prerequisites

```bash
echo "=== Checking prerequisites ==="
which git && echo "git: OK" || echo "git: MISSING"
which gh && echo "gh: OK" || echo "gh: MISSING"
which python3 && echo "python3: OK" || echo "python3: MISSING"
which bun && echo "bun: OK" || echo "bun: MISSING"
which docker && echo "docker: OK (optional)" || echo "docker: not found (optional)"
which claude && echo "claude: OK" || echo "claude: MISSING"
ls /Applications/Obsidian.app 2>/dev/null && echo "obsidian: OK" || echo "obsidian: not found (recommended)"
```

For each MISSING tool that is required (git, gh, python3, claude), call `/culver-bootstrap-local` or give the install command. Do not continue until git, gh, python3, and claude are present.

`bun` was installed by `install.sh` — if still missing, install: `curl -fsSL https://bun.sh/install | bash && source ~/.bashrc`

---

## Step 2: Ask the 10 onboarding questions

Ask ALL questions up front in a single AskUserQuestion call so the user can fill everything at once. Do not split into multiple rounds.

Questions to ask:
1. What is your name? (e.g. "Alex Reyes")
2. What do you want to call your admin agent? (e.g. "Atlas", "Nexus", "Orion", "Nova") — this name appears in Telegram and logs
3. What do you want to call your brain? (e.g. "cortex", "vault", "mind" — lowercase, no spaces) — prefix for your 3 ChromaDB collections
4. What projects are you working on? (name + one-line description, up to 3)
5. What habits do you want to track in your daily notes? (e.g. "Gym", "Meditation", "Reading")
6. Do you have Obsidian Desktop installed? What is the path to your vault? (e.g. ~/Documents/MyVault)
7. Do you have a GitHub account and a Personal Access Token (PAT) with repo + read:org scopes?
8. Do you have a VPS? (If yes: IP address + path to SSH key. If no: recommend Hostinger — Ubuntu 24.04, ~$4/mo)
9. Do you have a Telegram account and want to activate your admin bot? (If yes: give BotFather instructions to create the bot and get the token + group ID + thread ID)
10. Do you have a Gemini API key? (Free at aistudio.google.com — takes 1 minute)

---

## Step 3: Generate ~/.culver/config.json

```bash
mkdir -p "$HOME/.culver"
```

Using the answers from Step 2, write `~/.culver/config.json` following the schema in `~/.claude/skills/culver/config.template.json`. Replace every `{{PLACEHOLDER}}` with the user's actual values.

```bash
cat "$HOME/.culver/config.json"
```

Confirm the file looks correct before continuing.

---

## Step 4: Create private GitHub repos

```bash
# Authenticate gh CLI if needed
gh auth status 2>/dev/null || gh auth login

# Read username from config
GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
USERNAME=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['user']['name'].lower().replace(' ', ''))")

echo "Creating repos for $GITHUB_USER..."

# culver-os-{username} — private instance
gh repo create "$GITHUB_USER/culver-os-$USERNAME" --private 2>/dev/null && \
  echo "✅ Created culver-os-$USERNAME" || \
  echo "ℹ️  culver-os-$USERNAME already exists — will pull"

# agent-vault — wiki and raw sources
gh repo create "$GITHUB_USER/agent-vault" --private 2>/dev/null && \
  echo "✅ Created agent-vault" || \
  echo "ℹ️  agent-vault already exists — will pull"
```

---

## Step 5: Clone framework + parametrize

```bash
GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
USERNAME=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['user']['name'].lower().replace(' ', ''))")
INSTANCE_DIR="$HOME/culver-os-$USERNAME"
SKILLS_DIR="$HOME/.claude/skills/culver"

# Clone or update the user's private instance
if [ -d "$INSTANCE_DIR/.git" ]; then
  echo "Updating existing instance..."
  git -C "$INSTANCE_DIR" pull --rebase --quiet
else
  echo "Setting up instance directory..."
  mkdir -p "$INSTANCE_DIR"
  cp -r "$SKILLS_DIR/agents" "$INSTANCE_DIR/"
  cp -r "$SKILLS_DIR/scripts" "$INSTANCE_DIR/"
  cp -r "$SKILLS_DIR/tools" "$INSTANCE_DIR/"
  cp -r "$SKILLS_DIR/systemd" "$INSTANCE_DIR/"
  cp -r "$SKILLS_DIR/_templates" "$INSTANCE_DIR/"
  cp "$SKILLS_DIR/docker-compose.yml" "$INSTANCE_DIR/"
  cp "$SKILLS_DIR/requirements.txt" "$INSTANCE_DIR/"
  cp "$SKILLS_DIR/config.template.json" "$INSTANCE_DIR/"
  git -C "$INSTANCE_DIR" init --quiet
fi

# Parametrize: replace {{PLACEHOLDERS}} with user values
python3 "$SKILLS_DIR/scripts/parametrize.py" \
  --config "$HOME/.culver/config.json" \
  --dir "$INSTANCE_DIR"

echo "✅ Instance parametrized at $INSTANCE_DIR"
```

---

## Step 6: Set up Obsidian Git plugin (interactive)

If the user has Obsidian installed, guide them through installing the Obsidian Git plugin:

```
1. Open Obsidian
2. Go to Settings → Community Plugins → Browse
3. Search for "Obsidian Git" and install it
4. In plugin settings, set:
   - Auto save interval: 1 (minute)
   - Auto pull interval: 2 (minutes)
   - Pull on startup: enabled
5. Authenticate with GitHub (the plugin will ask for your PAT)
```

Verify the plugin is installed:
```bash
VAULT_PATH=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['obsidian']['vault_path'])")
ls "$VAULT_PATH/.obsidian/plugins/obsidian-git/manifest.json" 2>/dev/null && \
  echo "✅ Obsidian Git plugin found" || \
  echo "⚠️  Plugin not found yet — install it manually then continue"
```

---

## Step 7: Bootstrap VPS

If the user provided a VPS IP in Step 2, call `/culver-bootstrap-vps` now.

```bash
VPS_IP=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ip'])" 2>/dev/null)
if [ -n "$VPS_IP" ] && [ "$VPS_IP" != "{{VPS_IP}}" ]; then
  echo "VPS detected: $VPS_IP — calling /culver-bootstrap-vps"
else
  echo "No VPS configured — skipping VPS bootstrap"
  echo "You can run /culver-bootstrap-vps later to add a VPS."
fi
```

If VPS is present, invoke the Skill tool with `/culver-bootstrap-vps`. That skill handles the full VPS provisioning.

---

## Step 8: Final healthcheck

```bash
echo "=== Running healthcheck ==="
```

Invoke `/culver-healthcheck` to verify everything is working. Report results clearly.

---

## Step 9: Summary

Print a clean summary of what was set up:

```
✅ CulverOS setup complete!

Agent name:  {AGENT_NAME}
Brain name:  {BRAIN_NAME}
Instance:    ~/culver-os-{username}/
Config:      ~/.culver/config.json

VPS: {IP} — {status}
Telegram bot: {status}
ChromaDB: {status}
Timers: {count} active

Next steps:
- Open Telegram and talk to your {AGENT_NAME} bot
- Run /culver-daily to create today's note
- Run /culver-healthcheck anytime to check system status
```

---

## Error handling

- If `gh auth` fails: walk the user through `gh auth login` step by step
- If VPS SSH fails: check the SSH key path and VPS firewall (port 22 open)
- If ChromaDB doesn't respond: check that docker-compose is running on the VPS
- If Gemini API key is invalid: guide user to aistudio.google.com to get a free key
- Never stop the onboarding entirely — mark failed steps as ⚠️ and continue, then list what needs to be fixed at the end
