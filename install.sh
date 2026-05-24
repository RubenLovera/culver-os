#!/usr/bin/env bash
# CulverOS — Install Script
# Instala las Claude Code skills en ~/.claude/skills/culver/
# Usage: curl -fsSL https://raw.githubusercontent.com/RubenLovera/culver-os/main/install.sh | bash

set -e

SKILLS_DIR="$HOME/.claude/skills/culver"
REPO_URL="https://github.com/RubenLovera/culver-os"

# ── Colors ────────────────────────────────────────────────────────────────────

if [ -t 1 ]; then
  ORANGE='\033[38;5;214m'
  DIM='\033[2m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  ORANGE='' DIM='' BOLD='' RESET=''
fi

# ── Logo ──────────────────────────────────────────────────────────────────────

echo ""
printf "${ORANGE}"
printf '%s\n' ' ██████╗██╗   ██╗██╗     ██╗   ██╗███████╗██████╗    ██████╗ ███████╗'
printf '%s\n' '██╔════╝██║   ██║██║     ██║   ██║██╔════╝██╔══██╗  ██╔═══██╗██╔════╝'
printf '%s\n' '██║     ██║   ██║██║     ╚██╗ ██╔╝█████╗  ██████╔╝  ██║   ██║███████╗'
printf '%s\n' '██║     ██║   ██║██║      ╚████╔╝ ██╔══╝  ██╔══██╗  ██║   ██║╚════██║'
printf '%s\n' '╚██████╗╚██████╔╝███████╗  ╚██╔╝  ███████╗██║  ██║  ╚██████╔╝███████║'
printf '%s\n' ' ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═════╝ ╚══════╝'
printf "${RESET}"
printf "${DIM}%s${RESET}\n" '  v1.0  ·  Personal AI OS  ·  github.com/RubenLovera/culver-os'
echo ""

# ── Verificar Claude Code ──────────────────────────────────────────────────────

if ! command -v claude &>/dev/null; then
  echo "❌ Claude Code not found."
  echo "   Install it first: npm install -g @anthropic-ai/claude-code"
  echo "   Then re-run this installer."
  exit 1
fi

# ── Verificar git ──────────────────────────────────────────────────────────────

if ! command -v git &>/dev/null; then
  echo "❌ git not found. Please install git and try again."
  exit 1
fi

# ── Detectar bun ──────────────────────────────────────────────────────────────

if ! command -v bun &>/dev/null; then
  echo "📦 Installing bun..."
  curl -fsSL https://bun.sh/install | bash
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
  if ! command -v bun &>/dev/null; then
    echo "❌ bun installation failed. Install manually: https://bun.sh"
    exit 1
  fi
  echo "✅ bun installed"
fi

# ── Obsidian skills (kepano) ──────────────────────────────────────────────────

echo "📚 Installing Obsidian skills..."
if command -v npx &>/dev/null; then
  npx skills add https://github.com/kepano/obsidian-skills --quiet 2>/dev/null \
    || npx skills add https://github.com/kepano/obsidian-skills 2>&1 | tail -1 \
    || echo "⚠️  Could not install obsidian-skills — install manually: npx skills add https://github.com/kepano/obsidian-skills"
else
  echo "⚠️  npx not found — install obsidian skills manually: npx skills add https://github.com/kepano/obsidian-skills"
fi

# ── Clonar o actualizar ────────────────────────────────────────────────────────

if [ -d "$SKILLS_DIR/.git" ]; then
  echo "📂 Existing installation found — updating..."
  git -C "$SKILLS_DIR" pull --rebase --quiet
  echo "✅ Updated to latest"
else
  echo "📥 Cloning CulverOS..."
  mkdir -p "$HOME/.claude/skills"
  git clone --quiet "$REPO_URL" "$SKILLS_DIR"
  echo "✅ Cloned to $SKILLS_DIR"
fi

# ── Build ──────────────────────────────────────────────────────────────────────

if [ -f "$SKILLS_DIR/package.json" ]; then
  echo "🔨 Building..."
  cd "$SKILLS_DIR"
  bun install --quiet
  bun run build --quiet 2>/dev/null || true
fi

# ── Done ───────────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "${BOLD}%s${RESET}\n" "  Your OS is installed. Paste this into Claude Code to start setup:"
echo ""
printf "${ORANGE}%s${RESET}\n" "  Start setting up my Personal AI OS: read and follow ~/.claude/skills/culver/culver-onboarding/SKILL.md from start to finish — check prerequisites, ask me the setup questions, generate my config, create my GitHub repos, and deploy my VPS bots."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
