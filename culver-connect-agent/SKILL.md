---
name: culver-connect-agent
version: 1.0.0
description: |
  Guide to connect any Telegram bot or Python agent to your CulverBrain.
  Shows how to import tools/brain.py and tools/memory.py to get semantic
  search, interaction memory, and action logging in any agent.
allowed-tools:
  - Bash
  - Read
  - Write
---

# /culver-connect-agent

Connect your own bot or agent to the CulverBrain. This is simpler than it sounds:
you import two modules and your agent gets all 6 memory layers.

---

## Step 0: Understand the architecture

The brain runs on your VPS at `localhost:8000` (ChromaDB). Any process on the same VPS
can connect to it by importing `tools/brain.py` and `tools/memory.py`.

If your agent runs on a different machine, you'll need to expose ChromaDB externally
(see Step 4 below).

---

## Step 1: Read config

```bash
python3 -c "
import json
c = json.load(open('$HOME/.culver/config.json'))
print('BRAIN_NAME=' + c['agent']['brain_name'])
print('VPS_IP=' + c['vps']['ip'])
print('CULVER_OS_DIR=' + c['vps'].get('culver_os_dir', '/root/culver-os'))
"
```

---

## Step 2: Ask the user about their agent

Ask:
1. Does your agent run on the same VPS as CulverOS?
2. What language/framework is your agent written in? (Python / other)
3. What do you want the agent to do with the brain? (query, record interactions, log actions, all of the above)

---

## Step 3: Integration code (same-VPS Python agent)

If the agent runs on the same VPS, show this integration:

```python
import os
import sys

# Point to the CulverOS installation
CULVER_OS_DIR = os.getenv("CULVER_OS_DIR", "/root/culver-os")
sys.path.insert(0, CULVER_OS_DIR)

# ─── Capa 3: Query the semantic brain ──────────────────────────────────────
from tools.brain import query_filtered

def get_brain_context(user_message: str) -> str:
    results = query_filtered(user_message, top_n=5)
    if not results:
        return ""
    parts = ["[Relevant context from your vault:]"]
    for r in results[:3]:
        parts.append(r["document"][:600])
    return "\n\n".join(parts)

# ─── Capa 5: Record interactions (decisions, commitments) ──────────────────
from tools.memory import record_interaction, get_open_commitments

# Record something the user said
record_interaction(
    content="User decided to launch the product next Monday",
    interaction_type="commitment",   # decision | commitment | question | pattern
    source_bot="my-bot",
    topic="work",
    user_message=original_message,
)

# Get open commitments for morning kickoff
commitments = get_open_commitments(n=3)

# ─── Capa 6: Log actions (audit trail) ────────────────────────────────────
from tools.memory import record_action

record_action(
    action_type="message_sent",
    source_bot="my-bot",
    content=bot_response[:200],
    outcome="pending",
    message_id=telegram_message_id,
)
```

Required env var: `BRAIN_NAME` must match the brain prefix in your CulverOS config.

---

## Step 4: Integration for agent on a different machine

If the agent runs elsewhere, expose ChromaDB via SSH tunnel or update docker-compose:

### Option A: SSH tunnel (secure, no firewall changes)

```bash
# On your remote machine: tunnel VPS:8000 → localhost:8000
ssh -i ~/.ssh/your_key -N -L 8000:localhost:8000 root@{VPS_IP} &
```

Then in your agent, ChromaDB connects to `localhost:8000` as usual.

### Option B: Expose ChromaDB publicly (less secure)

Update `docker-compose.yml` on the VPS:
```yaml
chroma-server:
  ports:
    - "0.0.0.0:8000:8000"  # bind to all interfaces
```

Then in `tools/brain.py`, set `CHROMA_HOST` to the VPS IP:
```bash
export CHROMA_HOST={VPS_IP}
export CHROMA_PORT=8000
```

⚠️ If you expose ChromaDB publicly, add a firewall rule to only allow your agent's IP.

---

## Step 5: Verify the connection

```bash
SSH_KEY=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ssh_key'])")
VPS_IP=$(python3 -c "import json; c=json.load(open('$HOME/.culver/config.json')); print(c['vps']['ip'])")

ssh -i $SSH_KEY root@$VPS_IP "
source /root/culver-os/venv/bin/activate
python3 -c \"
import chromadb
client = chromadb.HttpClient(host='localhost', port=8000)
print('Collections:', client.list_collections())
print('✅ ChromaDB connection OK')
\"
"
```

---

## Step 6: Summary

Show the user a checklist:

```
✅ To connect your agent to CulverBrain:

1. sys.path.insert(0, CULVER_OS_DIR)
2. from tools.brain import query_filtered
3. from tools.memory import record_interaction, record_action
4. Set BRAIN_NAME env var to: {BRAIN_NAME}
5. Set CULVER_OS_DIR env var to: {CULVER_OS_DIR}

That's it. No registry, no API keys, no extra services.
```
