---
name: culver-brain-sync
version: 1.0.0
description: |
  Manually trigger a brain sync: pulls latest vaults from GitHub and re-indexes
  changed wiki/ files into ChromaDB. Use after adding many notes or when the
  brain feels outdated. The obsidian-brain-sync.timer runs this automatically every 2h.
allowed-tools:
  - Bash
  - Read
---

# /culver-brain-sync

Trigger a manual sync of the brain. Pulls the latest vault from GitHub onto the VPS,
detects changed wiki/ files, and re-indexes them into ChromaDB.

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
print('BRAIN_NAME=' + c['agent']['brain_name'])
"
```

Build SSH: `SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SSH_USER@$VPS_IP"`

---

## Step 1: Pull latest vault on VPS

```bash
$SSH "
cd $CULVER_OS_DIR/vaults/agent-vault
git pull --rebase --quiet && echo '✅ agent-vault updated'

cd $CULVER_OS_DIR/vaults/obsidian-vault 2>/dev/null && \
  git pull --rebase --quiet && echo '✅ obsidian-vault updated' || \
  echo '⚠️  obsidian-vault not cloned yet'
"
```

---

## Step 2: Detect changed wiki files

```bash
$SSH "
cd $CULVER_OS_DIR/vaults/agent-vault
echo '=== Changed wiki/ files (since last sync) ==='
git diff HEAD~1 HEAD --name-only -- wiki/ index/ 2>/dev/null | head -30 || \
  echo 'No git history or no changes detected — will do full rebuild check'
"
```

---

## Step 3: Run brain sync script

```bash
$SSH "
cd $CULVER_OS_DIR
source venv/bin/activate
python3 scripts/vault-brain-sync.py && echo '✅ Brain sync complete'
" 2>/dev/null || $SSH "
cd $CULVER_OS_DIR
source venv/bin/activate
# Fallback: run obsidian-brain-sync directly
python3 scripts/obsidian-brain-sync.py && echo '✅ Obsidian brain sync complete'
"
```

---

## Step 4: Verify ChromaDB has been updated

```bash
$SSH "
source $CULVER_OS_DIR/venv/bin/activate
python3 -c \"
import chromadb, os
client = chromadb.HttpClient(host='localhost', port=8000)
brain_name = open('$CULVER_OS_DIR/.env.admin').read()
# Get brain_name from env
for line in open('$CULVER_OS_DIR/.env.admin'):
    if line.startswith('BRAIN_NAME='):
        brain_name = line.strip().split('=')[1]
        break
col = client.get_or_create_collection(brain_name + '_brain')
count = col.count()
print(f'Brain collection: {brain_name}_brain — {count} chunks indexed')
\"
"
```

---

## Step 5: Report

```
✅ Brain sync complete

Brain: {BRAIN_NAME}_brain
Chunks indexed: {count}
Files re-indexed: {n changed files}
Last sync: {timestamp}

The brain is now up to date with your latest vault content.
```
