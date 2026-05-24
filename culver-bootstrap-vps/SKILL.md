---
name: culver-bootstrap-vps
version: 1.0.0
description: |
  Provisions a VPS and deploys the CulverOS runtime: admin bot, ChromaDB,
  and 12 systemd timers. Reads from ~/.culver/config.json.
  Called automatically by /culver-onboarding, or run standalone to add VPS later.
allowed-tools:
  - Bash
  - Read
  - Write
---

# /culver-bootstrap-vps

Provision the VPS and deploy the full CulverOS runtime. This skill:
1. Installs system dependencies (git, python3, docker)
2. Clones the user's private instance repo onto the VPS
3. Generates .env.admin from config.json
4. Starts docker-compose (ChromaDB + admin bot)
5. Generates and enables all 12 systemd timers
6. Verifies everything is running

Reads all config from `~/.culver/config.json`.

---

## Step 0: Read config

```bash
python3 -c "
import json
c = json.load(open('$HOME/.culver/config.json'))
vps = c['vps']
print('VPS_IP=' + vps['ip'])
print('SSH_KEY=' + vps['ssh_key'])
print('SSH_USER=' + vps.get('ssh_user', 'root'))
print('CULVER_OS_DIR=' + vps.get('culver_os_dir', '/root/culver-os'))
print('GITHUB_USER=' + c['github']['username'])
print('GITHUB_PAT=' + c['github']['pat'])
"
```

Export these values. Build SSH command:
```bash
VPS_IP=<from above>
SSH_KEY=<from above>
SSH_USER=<from above>
CULVER_OS_DIR=<from above>
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SSH_USER@$VPS_IP"
```

---

## Step 1: Verify SSH access

```bash
$SSH "echo 'SSH OK' && uname -a && free -h | head -2"
```

If this fails:
- Check that the SSH key path is correct
- Check that port 22 is open in the VPS firewall
- Try with `ubuntu` or `debian` user if `root` fails
- If Hostinger: go to hPanel → VPS → Firewall → add rule TCP 22 Any

Do not continue until SSH works.

---

## Step 2: Install system dependencies

```bash
$SSH "
apt-get update -qq && \
apt-get install -y -qq git python3 python3-pip python3-venv curl && \
echo '✅ Base packages OK'

# Docker
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  echo '✅ Docker installed'
else
  echo '✅ Docker already present'
fi

# docker compose v2
if ! docker compose version &>/dev/null; then
  apt-get install -y docker-compose-plugin
fi
echo '✅ docker compose OK'
"
```

---

## Step 3: Clone instance repo onto VPS

```bash
GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
USERNAME=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['user']['name'].lower().replace(' ', ''))")
GITHUB_PAT=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['pat'])")

REPO_URL="https://$GITHUB_PAT@github.com/$GITHUB_USER/culver-os-$USERNAME.git"

$SSH "
if [ -d '$CULVER_OS_DIR/.git' ]; then
  echo 'Updating existing clone...'
  cd $CULVER_OS_DIR && git pull --rebase --quiet
else
  echo 'Cloning instance repo...'
  git clone --quiet $REPO_URL $CULVER_OS_DIR
fi
echo '✅ Instance repo ready at $CULVER_OS_DIR'
"
```

---

## Step 4: Set up Python virtualenv and install requirements

```bash
$SSH "
cd $CULVER_OS_DIR
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo '✅ Python venv ready'
"
```

---

## Step 5: Generate .env.admin on VPS

Generate the env file locally first, then copy it to the VPS:

```bash
python3 "$HOME/.claude/skills/culver/scripts/generate_env.py" \
  "$HOME/.culver/config.json" \
  "/tmp/.env.admin"

scp -i $SSH_KEY /tmp/.env.admin $SSH_USER@$VPS_IP:$CULVER_OS_DIR/.env.admin
echo "✅ .env.admin uploaded to VPS"
rm /tmp/.env.admin
```

---

## Step 6: Create vault directories and clone both vaults

```bash
GITHUB_PAT=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['pat'])")
GITHUB_USER=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['github']['username'])")
AGENT_VAULT_REPO=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['agent_vault']['github_repo'].split('/')[-1])" 2>/dev/null || echo "agent-vault")

$SSH "
mkdir -p $CULVER_OS_DIR/vaults

# Clone personal-vault
PERSONAL_VAULT_URL='https://$GITHUB_PAT@github.com/$GITHUB_USER/personal-vault.git'
if [ -d '$CULVER_OS_DIR/vaults/personal-vault/.git' ]; then
  git -C $CULVER_OS_DIR/vaults/personal-vault pull --rebase --quiet
  echo '✅ personal-vault updated'
else
  git clone --quiet \$PERSONAL_VAULT_URL $CULVER_OS_DIR/vaults/personal-vault 2>/dev/null && \
    echo '✅ personal-vault cloned' || \
    echo '⚠️  personal-vault empty — will be populated by Obsidian Git plugin'
fi

# Clone agent-vault
AGENT_VAULT_URL='https://$GITHUB_PAT@github.com/$GITHUB_USER/$AGENT_VAULT_REPO.git'
if [ -d '$CULVER_OS_DIR/vaults/$AGENT_VAULT_REPO/.git' ]; then
  git -C $CULVER_OS_DIR/vaults/$AGENT_VAULT_REPO pull --rebase --quiet
  echo '✅ agent-vault updated'
else
  git clone --quiet \$AGENT_VAULT_URL $CULVER_OS_DIR/vaults/$AGENT_VAULT_REPO 2>/dev/null || \
    mkdir -p $CULVER_OS_DIR/vaults/$AGENT_VAULT_REPO
  echo '✅ agent-vault ready'
fi
"
```

**Initialize agent vault structure** if this is a fresh vault (no CLAUDE.md yet):

```bash
$SSH "
AGENT_PATH=$CULVER_OS_DIR/vaults/$AGENT_VAULT_REPO

if [ ! -f \"\$AGENT_PATH/CLAUDE.md\" ]; then
  echo 'Initializing agent vault structure...'
  cd $CULVER_OS_DIR
  source venv/bin/activate

  # Copy templates to agent vault
  mkdir -p \$AGENT_PATH/raw/articles \$AGENT_PATH/raw/transcripts \$AGENT_PATH/raw/notes \$AGENT_PATH/raw/personal_vault_sync
  mkdir -p \$AGENT_PATH/wiki \$AGENT_PATH/outputs \$AGENT_PATH/index/supervisor-reports \$AGENT_PATH/_templates

  cp $CULVER_OS_DIR/_templates/agent-vault-CLAUDE.md \$AGENT_PATH/CLAUDE.md
  cp $CULVER_OS_DIR/_templates/MASTER_INDEX.md \$AGENT_PATH/index/MASTER_INDEX.md
  cp $CULVER_OS_DIR/_templates/INGEST_QUEUE.md \$AGENT_PATH/index/INGEST_QUEUE.md
  cp $CULVER_OS_DIR/_templates/agent-article.md \$AGENT_PATH/_templates/article.md
  cp $CULVER_OS_DIR/_templates/agent-concept.md \$AGENT_PATH/_templates/concept.md

  # Create empty log
  TODAY=\$(date +%Y-%m-%d)
  echo '# Agent Vault — Operations Log' > \$AGENT_PATH/index/log.md
  echo '' >> \$AGENT_PATH/index/log.md
  echo \"## [\$TODAY] init | vault initialized\" >> \$AGENT_PATH/index/log.md

  # Parametrize CLAUDE.md with actual values
  python3 $CULVER_OS_DIR/scripts/parametrize.py --config /tmp/culver-config.json --dir \$AGENT_PATH 2>/dev/null || true

  # Commit and push initial structure
  cd \$AGENT_PATH
  git init --quiet 2>/dev/null || true
  git remote add origin \$AGENT_VAULT_URL 2>/dev/null || true
  git add -A
  git commit -m 'init: agent vault structure from culver-bootstrap-vps' --quiet
  git push origin main --quiet 2>/dev/null || git push origin master --quiet 2>/dev/null || true

  echo '✅ Agent vault initialized and pushed'
else
  echo '✅ Agent vault already initialized'
fi
"
```

---

## Step 7: Start docker-compose (ChromaDB + admin bot)

```bash
$SSH "
cd $CULVER_OS_DIR
docker compose up -d
echo '✅ docker-compose started'
sleep 5
docker compose ps
"
```

Verify ChromaDB is responding:
```bash
$SSH "curl -s http://localhost:8000/api/v1/heartbeat && echo '' && echo '✅ ChromaDB responding'"
```

---

## Step 8: Generate and enable systemd timers

```bash
# Copy config.json to VPS temporarily for timer generation
scp -i $SSH_KEY "$HOME/.culver/config.json" "$SSH_USER@$VPS_IP:/tmp/culver-config.json"

$SSH "
cd $CULVER_OS_DIR
source venv/bin/activate
python3 scripts/generate_timers.py /tmp/culver-config.json
rm /tmp/culver-config.json
"
```

---

## Step 9: Verify all services

```bash
$SSH "
echo '=== Docker services ==='
docker compose -f $CULVER_OS_DIR/docker-compose.yml ps

echo ''
echo '=== Systemd timers ==='
systemctl list-timers --no-pager | grep -E 'daily-note|vault-ingest|vault-health|obsidian-brain|weekly|monthly|log-rotate|status-op|perfil' || echo 'no timers found'

echo ''
echo '=== ChromaDB heartbeat ==='
curl -s http://localhost:8000/api/v1/heartbeat && echo ''
"
```

---

## Step 10: Report

Report status clearly:

```
✅ VPS Bootstrap Complete

VPS: {IP}
Admin bot: ✅ running / ⚠️ error
ChromaDB: ✅ running / ⚠️ error
Timers enabled: {count}/12

Next: open Telegram and send a message to your {AGENT_NAME} bot.
```

If anything failed, show the exact error and the fix command. Do not leave the user with an incomplete setup without a clear next step.
