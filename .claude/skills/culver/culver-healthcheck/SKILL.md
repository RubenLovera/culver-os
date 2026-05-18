---
name: culver-healthcheck
version: 1.0.0
description: |
  Check status of all CulverOS services: admin bot, ChromaDB, 12 systemd timers.
  Reads VPS config from ~/.culver/config.json.
  Reports: OK / WARNING / CRITICAL with actionable fixes for each issue.
allowed-tools:
  - Bash
  - Read
---

# /culver-healthcheck

Check the health of the entire CulverOS runtime. Report clearly: what's running, what's not, and how to fix it.

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
print('AGENT_NAME=' + c['agent']['name'])
"
```

Build SSH command: `SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SSH_USER@$VPS_IP"`

---

## Step 1: Check VPS connectivity

```bash
$SSH "echo 'VPS reachable' && uptime" 2>/dev/null || echo "❌ VPS unreachable"
```

If unreachable:
- Try `ping $VPS_IP`
- Check if port 22 is open: `nc -zv $VPS_IP 22`
- If Hostinger: check hPanel → VPS → status

---

## Step 2: Check Docker services

```bash
$SSH "
cd $CULVER_OS_DIR
echo '=== Docker services ==='
docker compose ps --format 'table {{.Name}}\t{{.Status}}'

echo ''
echo '=== ChromaDB heartbeat ==='
curl -s http://localhost:8000/api/v1/heartbeat && echo ' ✅' || echo ' ❌ ChromaDB not responding'
"
```

---

## Step 3: Check systemd timers

```bash
$SSH "
echo '=== Active timers ==='
systemctl list-timers --no-pager | grep -E 'daily-note|vault-ingest|vault-health|obsidian-brain|weekly|monthly|log-rotate|status-op|perfil'

echo ''
echo '=== Timer last runs (past 24h) ==='
journalctl --since '24 hours ago' -u 'daily-note.service' -u 'vault-ingest.service' -u 'vault-health.service' --no-pager | tail -20
"
```

Flag any timer not listed as ACTIVE, and any timer whose last run is >36 hours ago.

---

## Step 4: Check recent bot logs

```bash
$SSH "
echo '=== Admin bot logs (last 20 lines) ==='
docker compose logs admin-bot --tail=20 2>/dev/null || journalctl -u admin-bot --no-pager -n 20
"
```

Look for: ERROR, CRITICAL, Traceback, 429. Report any errors found.

---

## Step 5: Report

Produce a clean status report:

```
=== CulverOS Health Check — {DATE} ===

VPS: {IP} — ✅ reachable / ❌ unreachable
ChromaDB: ✅ running / ❌ down
Admin bot ({AGENT_NAME}): ✅ running / ❌ down

Timers (12 total):
  ✅ daily-note — last run: {X}h ago
  ✅ vault-ingest — last run: {X}h ago
  ✅ vault-health — last run: {X}h ago
  ✅ obsidian-brain-sync — last run: {X}h ago
  ...

Issues:
  [list any ⚠️ or ❌ with fix commands]

Overall: ✅ OK / 🟡 WARNING / 🔴 CRITICAL
```

For each issue, include the exact command to fix it. Never leave a ❌ without a suggested fix.
