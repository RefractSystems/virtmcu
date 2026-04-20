#!/usr/bin/env bash
set -e

echo "==> Configuring Git..."
git config --global credential.https://github.com.helper ''
git config --global credential.helper '!gh auth git-credential'
git config --global --add safe.directory /workspace

# Set Git identity if missing globally
if [ -z "$(git config --global user.email)" ]; then
    echo "    Detecting Git identity from GitHub..."
    GH_USER_JSON=$(gh api user 2>/dev/null || echo "{}")
    if [ "$GH_USER_JSON" != "{}" ]; then
        GH_NAME=$(echo "$GH_USER_JSON" | jq -r '.name // .login')
        GH_EMAIL=$(echo "$GH_USER_JSON" | jq -r '.email // empty')
        
        if [ -z "$GH_EMAIL" ]; then
            GH_LOGIN=$(echo "$GH_USER_JSON" | jq -r '.login')
            GH_ID=$(echo "$GH_USER_JSON" | jq -r '.id')
            GH_EMAIL="${GH_ID}+${GH_LOGIN}@users.noreply.github.com"
        fi
        
        git config --global user.name "$GH_NAME"
        git config --global user.email "$GH_EMAIL"
        echo "    Set Git identity to: $GH_NAME <$GH_EMAIL>"
    else
        echo "    Warning: Could not detect GitHub identity. Please run 'git config --global user.email \"you@example.com\"'."
    fi
fi

echo "==> Synchronizing Python Environment..."
uv sync
echo '[ -f /workspace/.venv/bin/activate ] && source /workspace/.venv/bin/activate' >> ~/.zshrc
echo 'set -a; [ -f /workspace/.env ] && source /workspace/.env; set +a' >> ~/.zshrc

echo "==> Installing AI Developer Tools (Claude Code & Gemini CLI)..."
sudo npm install -g @google/gemini-cli@latest
curl -fsSL https://claude.ai/install.sh | bash
echo "alias gemini='gemini --yolo'" >> ~/.zshrc
echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.zshrc

echo "==> Installing Git Hooks..."
make install-hooks

echo "✓ DevContainer initialization complete."
