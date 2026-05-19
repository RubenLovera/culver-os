---
name: culver-add-connector
version: 1.0.0
description: |
  Interactive wizard to enable an existing connector or guide building a new one.
  Connectors deposit files into raw/ for vault-ingest.py to process.
  Available pre-built connectors: obsidian_sync. Others: notion, gmail, github, granola (v1+).
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /culver-add-connector

Add a new data source to your CulverOS ingestion pipeline.

---

## Step 1: Show available connectors

List what's available vs what's enabled:

```bash
VPS_IP=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ip'])" 2>/dev/null)
SSH_KEY=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ssh_key'])" 2>/dev/null)
CULVER_DIR=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps'].get('culver_os_dir', '/root/culver-os'))" 2>/dev/null)
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no root@$VPS_IP"

# Show pre-built connectors
echo "=== Pre-built connectors ==="
ls $HOME/.claude/skills/culver/connectors/*.py 2>/dev/null | xargs -I{} basename {} .py | grep -v __init__ | grep -v base

# Show enabled connectors in config.json
echo ""
echo "=== Currently enabled ==="
python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c.get('connectors', {}).get('enabled', []))" 2>/dev/null
```

---

## Step 2: Ask what the user wants to do

Use AskUserQuestion to determine:
- Enable a pre-built connector (obsidian_sync, etc.)
- Build a custom connector (user provides their source)

---

## Step 3a: Enable a pre-built connector

If enabling an existing connector:

```bash
CONNECTOR_NAME="<connector_name>"  # from user selection

# Add to config.json
python3 -c "
import json
config_path = '$HOME/.culver/config.json'
c = json.load(open(config_path))
if 'connectors' not in c:
    c['connectors'] = {'enabled': []}
if CONNECTOR_NAME not in c['connectors']['enabled']:
    c['connectors']['enabled'].append('$CONNECTOR_NAME')
with open(config_path, 'w') as f:
    json.dump(c, f, indent=2)
print('Updated config.json')
"
```

Show the connector's default config and ask the user to fill any required values.
Update config.json with the connector's settings section.

Sync config to VPS:
```bash
scp -i $SSH_KEY "$HOME/.culver/config.json" "root@$VPS_IP:$CULVER_DIR/config.json"
echo "✅ config synced to VPS"
```

Test the connector:
```bash
$SSH "
cd $CULVER_DIR
source venv/bin/activate
python3 -c \"
import json, sys
sys.path.insert(0, '.')
config = json.load(open('config.json'))
from connectors.$CONNECTOR_NAME import *
import importlib
mod = importlib.import_module('connectors.$CONNECTOR_NAME')
# Find the connector class
cls = [v for k,v in vars(mod).items() if isinstance(v, type) and hasattr(v, 'run') and k != 'BaseConnector'][0]
c = cls()
ok = c.validate_config(config.get('connectors', {}).get('$CONNECTOR_NAME', {}))
print('validate_config:', ok)
\"
"
```

---

## Step 3b: Build a custom connector

If building a new connector:

1. Read `connectors/README.md` and explain the interface to the user
2. Ask: what is the source? what data should it pull? where should files go in raw/?
3. Generate the connector file from the README template
4. Test it with `validate_config` and a dry-run `run()`

```bash
cat $HOME/.claude/skills/culver/connectors/README.md
```

Create the connector file at `connectors/{name}.py` following the README spec.
Add it to `connectors.enabled` in config.json.
Upload to VPS:
```bash
scp -i $SSH_KEY "$HOME/.claude/skills/culver/connectors/$CONNECTOR_NAME.py" \
  "root@$VPS_IP:$CULVER_DIR/connectors/$CONNECTOR_NAME.py"
```

---

## Step 4: Run a test ingest

```bash
$SSH "
cd $CULVER_DIR
source venv/bin/activate
python3 scripts/vault-ingest.py 2>&1 | head -30
"
```

Report what files were deposited and whether ingest processed them.

---

## Step 5: Summary

Report clearly:
- Connector enabled: {name}
- Files it will deposit in raw/{subfolder}/
- When it runs: on next vault-ingest.py execution (daily 12:00 UTC, or /culver-ingest to trigger now)
