---
name: culver-bootstrap-local
version: 1.0.0
description: |
  Install local prerequisites for CulverOS on Mac or Linux.
  Installs: git, gh CLI, python3, bun, docker, and verifies Obsidian and Claude Code.
  Called automatically by /culver-onboarding when prerequisites are missing.
allowed-tools:
  - Bash
---

# /culver-bootstrap-local

Install the local prerequisites needed for CulverOS. Detects OS and installs what's missing.

---

## Step 1: Detect OS

```bash
OS=$(uname -s)
echo "OS: $OS"
if [ "$OS" = "Darwin" ]; then
  echo "Platform: macOS"
  command -v brew &>/dev/null && echo "brew: OK" || echo "brew: MISSING"
elif [ "$OS" = "Linux" ]; then
  echo "Platform: Linux"
  command -v apt-get &>/dev/null && echo "apt: OK"
fi
```

---

## Step 2: Install missing tools

### macOS

```bash
# Install Homebrew if missing
if ! command -v brew &>/dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install tools
command -v git &>/dev/null || brew install git
command -v gh &>/dev/null || brew install gh
command -v python3 &>/dev/null || brew install python3

# bun
command -v bun &>/dev/null || curl -fsSL https://bun.sh/install | bash

# Docker Desktop (manual — can't install headlessly on Mac)
if ! command -v docker &>/dev/null; then
  echo "⚠️  Docker Desktop not found."
  echo "   Download: https://www.docker.com/products/docker-desktop/"
  echo "   Docker is optional — the VPS uses it, not your Mac."
fi
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-pip curl

# gh CLI
if ! command -v gh &>/dev/null; then
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
  sudo apt-get update -qq && sudo apt-get install -y gh
fi

# bun
command -v bun &>/dev/null || curl -fsSL https://bun.sh/install | bash
```

---

## Step 3: Authenticate gh CLI

```bash
gh auth status 2>/dev/null && echo "✅ gh authenticated" || gh auth login
```

---

## Step 4: Verify all tools

```bash
echo "=== Final check ==="
for tool in git gh python3 bun claude; do
  command -v $tool &>/dev/null && echo "✅ $tool" || echo "❌ $tool — MISSING"
done
```

---

## Step 5: Report

List what's installed and what's still missing. For anything still missing, give the exact install command. Return control to `/culver-onboarding`.
