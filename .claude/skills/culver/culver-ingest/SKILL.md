---
name: culver-ingest
version: 1.0.0
description: |
  Manually triggers vault-ingest.py on the VPS — processes pending raw/ files
  into wiki pages. Shows progress and lists created pages.
  Use when you want to ingest new content without waiting for the 12:00 UTC timer.
allowed-tools:
  - Bash
  - Read
---

# /culver-ingest

Trigger the vault ingestion pipeline on the VPS manually.

---

## Step 1: Check pending files

```bash
VPS_IP=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ip'])" 2>/dev/null)
SSH_KEY=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ssh_key'])" 2>/dev/null)
CULVER_DIR=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps'].get('culver_os_dir', '/root/culver-os'))" 2>/dev/null)
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no root@$VPS_IP"

$SSH "
cd $CULVER_DIR
source venv/bin/activate
AGENT_PATH=\$(grep AGENT_VAULT_PATH .env.admin | cut -d= -f2)
echo '=== Files in raw/ ==='
find \$AGENT_PATH/raw -name '*.md' | wc -l
echo 'files total'
echo ''
echo '=== Already processed (in log.md) ==='
grep -c '## \[' \$AGENT_PATH/index/log.md 2>/dev/null || echo 0
echo 'entries'
"
```

Report how many files are pending (total raw - already in log).

---

## Step 2: Run vault-ingest.py

```bash
$SSH "
cd $CULVER_DIR
source venv/bin/activate
python3 scripts/vault-ingest.py 2>&1
"
```

Stream the output. Show clearly:
- How many files were processed
- Which wiki pages were created (paths)
- Any errors

---

## Step 3: Show results

```bash
$SSH "
cd $CULVER_DIR
source venv/bin/activate
AGENT_PATH=\$(grep AGENT_VAULT_PATH .env.admin | cut -d= -f2)
echo '=== New wiki pages ==='
find \$AGENT_PATH/wiki -name '*.md' -newer \$AGENT_PATH/index/RECENT_UPDATES.md 2>/dev/null | head -20
echo ''
echo '=== RECENT_UPDATES ==='
cat \$AGENT_PATH/index/RECENT_UPDATES.md 2>/dev/null | head -30
"
```

Report a clean summary: N files processed → N wiki pages created.
If there were errors, show them and suggest fixes.
