#!/usr/bin/env sh
set -e

REPO_URL="${PAULDOT_REPO:-}"

cat <<'EOF'
pauldot bootstrap
─────────────────
This will:
  1. Install uv (if missing)
  2. Install pauldot via uv
  3. Clone your dotfiles repo
  4. Run pauldot apply

If your dotfiles repo is PRIVATE, you'll need GitHub CLI authentication.
After this script installs pauldot, run:

    pauldot help gh

…to walk through gh setup before re-running this script with PAULDOT_REPO set.

EOF

if [ -z "$REPO_URL" ]; then
  printf "Dotfiles repo URL (or Ctrl-C to abort and run 'pauldot help gh' first): "
  read -r REPO_URL
fi

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
  echo "→ Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2. pauldot
echo "→ Installing pauldot"
uv tool install pauldot

# 3. clone & init
echo "→ Initialising dotfiles"
pauldot init "$REPO_URL"

# 4. apply
echo "→ Applying"
pauldot apply

echo "✓ Done. Open a new shell or run 'source ~/.zshrc'."
