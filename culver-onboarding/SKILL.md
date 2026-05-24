---
name: culver-onboarding
version: 1.1.0
description: |
  Complete setup wizard for your Personal AI OS. Asks all questions at once,
  then runs end-to-end without stopping: generates ~/.culver/config.json,
  creates private GitHub repos, parametrizes the framework, and deploys
  the VPS runtime. Run once after installing CulverOS.
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

**Run each step in order. After the single question round, execute everything
without pausing for confirmation. Report what you did at each step.**

---

## Preamble: Show logo + check state

```bash
ORANGE='\033[38;5;214m'; RESET='\033[0m'
printf "${ORANGE}"
printf '%s\n' ' ██████╗██╗   ██╗██╗     ██╗   ██╗███████╗██████╗    ██████╗ ███████╗'
printf '%s\n' '██╔════╝██║   ██║██║     ██║   ██║██╔════╝██╔══██╗  ██╔═══██╗██╔════╝'
printf '%s\n' '██║     ██║   ██║██║     ╚██╗ ██╔╝█████╗  ██████╔╝  ██║   ██║███████╗'
printf '%s\n' '██║     ██║   ██║██║      ╚████╔╝ ██╔══╝  ██╔══██╗  ██║   ██║╚════██║'
printf '%s\n' '╚██████╗╚██████╔╝███████╗  ╚██╔╝  ███████╗██║  ██║  ╚██████╔╝███████║'
printf '%s\n' ' ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═════╝ ╚══════╝'
printf "${RESET}\n"

echo "Setting up your Personal AI OS..."
echo ""

# Check existing config
if [ -f "$HOME/.culver/config.json" ]; then
  echo "EXISTING_CONFIG=true"
  cat "$HOME/.culver/config.json"
else
  echo "EXISTING_CONFIG=false"
fi

# Quick prereq scan
echo ""
echo "=== Prerequisites ==="
command -v git   >/dev/null 2>&1 && echo "git: ok"    || echo "git: MISSING"
command -v gh    >/dev/null 2>&1 && echo "gh: ok"     || echo "gh: MISSING"
command -v python3 >/dev/null 2>&1 && echo "python3: ok" || echo "python3: MISSING"
command -v claude >/dev/null 2>&1 && echo "claude: ok" || echo "claude: MISSING"
ls /Applications/Obsidian.app 2>/dev/null && echo "obsidian: ok" || echo "obsidian: not found (recommended)"
```

Read the output:

- If `EXISTING_CONFIG=true` and the config looks complete (no `{{PLACEHOLDER}}` remaining): tell the user and skip to **Step 5 (Bootstrap VPS)** if VPS is not yet deployed, or run **Step 7 (Healthcheck)** if everything looks deployed.
- If any required tool is MISSING (git, gh, python3, claude): tell the user which ones and stop. They must install them before continuing.
- Otherwise proceed immediately to **Step 1**.

---

## Step 1: Ask everything at once

Ask ALL questions in a **single AskUserQuestion call**. Do not split into multiple rounds.
Mark optional fields clearly so the user can skip them.

Questions:

1. **Your name** — e.g. "Alex Reyes" (used in your daily notes and agent memory)
2. **Agent name** — what do you want to call your 24/7 admin agent? (e.g. Atlas, Nexus, Nova) — appears in Telegram and logs
3. **Brain name** — lowercase, no spaces (e.g. cortex, vault, mind) — prefix for your 3 ChromaDB collections
4. **Projects** — up to 3 projects with a one-line description each (e.g. "Acme — B2B SaaS")
5. **Daily habits to track** — e.g. Gym, Meditation, Reading
6. **Obsidian personal vault path** — local path to your existing vault (e.g. ~/Documents/MyVault) or "none"
7. **GitHub username + Personal Access Token** — token needs repo + read:org scopes. Get one at github.com/settings/tokens
8. **VPS IP + SSH key path** — (optional) Ubuntu 24.04 VPS. If none, type "skip" — you can add one later with `/culver-bootstrap-vps`
9. **Telegram** — (optional) Telegram group ID + bot tokens for admin/diario/finno/jobs bots. Type "skip" to set up later.
10. **LLM API key** — for the ingestion pipeline. Options: Gemini (free at aistudio.google.com, recommended), Claude (anthropic.com), or OpenAI. Which provider and key?
11. **Agent vault repo name** — name for the GitHub repo where your AI-compiled wiki lives (default: agent-vault)

---

## Step 2: Generate ~/.culver/config.json

```bash
mkdir -p "$HOME/.culver"
```

Using the answers from Step 1, write `~/.culver/config.json` following the schema in
`~/.claude/skills/culver/config.template.json`. Replace every `{{PLACEHOLDER}}` with
the user's actual values. For skipped optional fields, keep the `{{PLACEHOLDER}}` as-is.

Do not pause to confirm — write the file and continue immediately to Step 3.

---

## Step 3: Create private GitHub repos

```bash
gh auth status 2>/dev/null || gh auth login

GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
USERNAME=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['user']['name'].lower().replace(' ', ''))")
AGENT_VAULT_REPO=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['agent_vault']['github_repo'].split('/')[-1])" 2>/dev/null || echo "agent-vault")

gh repo create "$GITHUB_USER/culver-os-$USERNAME" --private 2>/dev/null && \
  echo "✅ Created culver-os-$USERNAME" || \
  echo "ℹ️  culver-os-$USERNAME already exists"

gh repo create "$GITHUB_USER/personal-vault" --private 2>/dev/null && \
  echo "✅ Created personal-vault" || \
  echo "ℹ️  personal-vault already exists"

gh repo create "$GITHUB_USER/$AGENT_VAULT_REPO" --private 2>/dev/null && \
  echo "✅ Created $AGENT_VAULT_REPO" || \
  echo "ℹ️  $AGENT_VAULT_REPO already exists"
```

Continue immediately after — do not wait for user confirmation.

---

## Step 4: Clone framework + parametrize

```bash
GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
USERNAME=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['user']['name'].lower().replace(' ', ''))")
INSTANCE_DIR="$HOME/culver-os-$USERNAME"
SKILLS_DIR="$HOME/.claude/skills/culver"

if [ -d "$INSTANCE_DIR/.git" ]; then
  echo "Updating existing instance..."
  git -C "$INSTANCE_DIR" pull --rebase --quiet
else
  echo "Setting up instance..."
  mkdir -p "$INSTANCE_DIR"
  for d in agents scripts tools systemd _templates connectors; do
    [ -d "$SKILLS_DIR/$d" ] && cp -r "$SKILLS_DIR/$d" "$INSTANCE_DIR/"
  done
  for f in docker-compose.yml requirements.txt config.template.json; do
    [ -f "$SKILLS_DIR/$f" ] && cp "$SKILLS_DIR/$f" "$INSTANCE_DIR/"
  done
  git -C "$INSTANCE_DIR" init --quiet
fi

python3 "$SKILLS_DIR/scripts/parametrize.py" \
  --config "$HOME/.culver/config.json" \
  --dir "$INSTANCE_DIR"

echo "✅ Instance ready at $INSTANCE_DIR"
```

After parametrizing, push the instance to the user's private repo:

```bash
GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
USERNAME=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['user']['name'].lower().replace(' ', ''))")
INSTANCE_DIR="$HOME/culver-os-$USERNAME"

cd "$INSTANCE_DIR"
git remote get-url origin >/dev/null 2>&1 || \
  git remote add origin "https://github.com/$GITHUB_USER/culver-os-$USERNAME.git"
git add -A
git commit -m "chore: initial parametrized instance" --quiet 2>/dev/null || true
git push -u origin main --quiet 2>/dev/null || git push -u origin master --quiet 2>/dev/null || true
echo "✅ Instance pushed to GitHub"
```

---

## Step 5: Bootstrap VPS

```bash
VPS_IP=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ip'])" 2>/dev/null || echo "")
```

- If VPS_IP is empty or still a `{{PLACEHOLDER}}`: print "⏭ No VPS configured — skipping. Run /culver-bootstrap-vps later to add one." and continue.
- If VPS_IP is a real IP: invoke the `/culver-bootstrap-vps` skill now. That skill handles full VPS provisioning end-to-end.

---

## Step 6: Setup Obsidian Git (informational, non-blocking)

If the user has Obsidian installed, print these instructions (do not wait for them to complete):

```
To sync your personal vault with GitHub:
1. Open Obsidian → Settings → Community Plugins → Browse → search "Obsidian Git" → Install
2. Plugin settings: Auto save 1 min, Auto pull 2 min, Pull on startup ON
3. Authenticate with your GitHub PAT
4. Run "Initialize repo" — it will sync to {GITHUB_USER}/personal-vault
```

```bash
VAULT_PATH=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['personal_vault']['local_path'])" 2>/dev/null || echo "")
if [ -n "$VAULT_PATH" ] && [ "$VAULT_PATH" != "{{PERSONAL_VAULT_LOCAL_PATH}}" ]; then
  ls "$VAULT_PATH/.obsidian/plugins/obsidian-git/manifest.json" 2>/dev/null && \
    echo "✅ Obsidian Git plugin already installed" || \
    echo "ℹ️  Obsidian Git not yet installed in your vault — see instructions above"
fi
```

Continue immediately — do not wait for Obsidian to be configured.

---

## Step 7: Healthcheck

```bash
echo "=== Running healthcheck ==="
```

Invoke `/culver-healthcheck` to verify what was set up. Report results.

---

## Step 8: Summary

Print a clean summary:

```
✅ CulverOS setup complete!

Agent:      {AGENT_NAME}
Brain:      {BRAIN_NAME}
Instance:   ~/culver-os-{username}/
Config:     ~/.culver/config.json

VPS:            {ip} — {deployed/skipped}
Telegram bots:  {configured/skipped}
ChromaDB:       {running/skipped}

Next:
  → Open Telegram and talk to your {AGENT_NAME} bot
  → Run /culver-daily to create today's note
  → Run /culver-healthcheck anytime to check system status
  → Run /culver-brain-sync to index your knowledge base
```

---

## Error handling

- If `gh auth` fails: walk through `gh auth login --web` step by step
- If VPS SSH fails: check SSH key path and VPS firewall (port 22)
- If ChromaDB doesn't respond: check docker-compose is running on VPS
- If Gemini API key invalid: guide to aistudio.google.com for a free key
- Never stop the onboarding entirely — mark failed steps as ⚠️, continue, and list what needs fixing at the end
