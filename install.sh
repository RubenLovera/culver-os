#!/usr/bin/env bash
# CulverOS — Install Script
# Instala las Claude Code skills en ~/.claude/skills/culver/
# Usage: curl -fsSL https://raw.githubusercontent.com/RubenLovera/culver-os/main/install.sh | bash

set -e

SKILLS_DIR="$HOME/.claude/skills/culver"
REPO_URL="https://github.com/RubenLovera/culver-os"
REPO_RAW="https://raw.githubusercontent.com/RubenLovera/culver-os/main"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       CulverOS — Installing Skills       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Verificar Claude Code ──────────────────────────────────────────────────

if ! command -v claude &>/dev/null; then
  echo "❌ Claude Code not found."
  echo "   Install it first: npm install -g @anthropic-ai/claude-code"
  echo "   Then re-run this installer."
  exit 1
fi

# ── Verificar git ──────────────────────────────────────────────────────────

if ! command -v git &>/dev/null; then
  echo "❌ git not found. Please install git and try again."
  exit 1
fi

# ── Detectar bun (necesario para build de skills) ─────────────────────────

if ! command -v bun &>/dev/null; then
  echo "📦 bun not found — installing..."
  curl -fsSL https://bun.sh/install | bash
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
  if ! command -v bun &>/dev/null; then
    echo "❌ bun installation failed. Please install manually: https://bun.sh"
    exit 1
  fi
  echo "✅ bun installed"
fi

# ── Clonar o actualizar el repo ────────────────────────────────────────────

if [ -d "$SKILLS_DIR/.git" ]; then
  echo "📂 Existing installation found — updating..."
  git -C "$SKILLS_DIR" pull --rebase --quiet
  echo "✅ Updated to latest"
else
  echo "📥 Cloning CulverOS skills..."
  mkdir -p "$HOME/.claude/skills"
  git clone --quiet "$REPO_URL" "$SKILLS_DIR"
  echo "✅ Cloned to $SKILLS_DIR"
fi

# ── Build de skills ────────────────────────────────────────────────────────

if [ -f "$SKILLS_DIR/package.json" ]; then
  echo "🔨 Building skills..."
  cd "$SKILLS_DIR"
  bun install --quiet
  bun run build --quiet 2>/dev/null || true
  echo "✅ Build complete"
fi

# ── Done ───────────────────────────────────────────────────────────────────

echo ""
echo "✅ CulverOS skills installed successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Next step: open Claude Code and run"
echo ""
echo "    /culver-onboarding"
echo ""
echo "  This will set up your Personal AI OS"
echo "  in about 10 minutes."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
