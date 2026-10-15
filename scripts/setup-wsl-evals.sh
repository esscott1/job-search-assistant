#!/usr/bin/env bash
# One-time setup for running `claude plugin eval` (with shell-using cases) inside WSL Ubuntu.
# On Windows the eval runner refuses to grant a shell (no OS sandbox), so cases that run
# scripts such as score.py must run under WSL, Linux or macOS.
# Run inside Ubuntu (WSL) from the repo root:  bash scripts/setup-wsl-evals.sh
set -euo pipefail

echo "== 1/4 System packages (asks for your Ubuntu password)"
sudo apt-get update -y
# bubblewrap + socat: the sandbox Claude Code needs before it will grant a shell to an eval run.
sudo apt-get install -y bubblewrap socat python3 curl ca-certificates git
# python-docx, LibreOffice and pdfinfo: the resume builder's evals build a real .docx and count its pages.
sudo apt-get install -y python3-docx libreoffice-writer-nogui poppler-utils

echo "== 2/4 Node.js 22 via nvm (no sudo)"
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm install 22
nvm alias default 22

echo "== 3/4 Claude Code (same version CI pins)"
npm install -g @anthropic-ai/claude-code@2.1.289
claude --version

echo "== 4/4 Check the sandbox backend and resume tools"
bwrap --version
python3 --version
python3 -c "import docx; print('python-docx ok')"
soffice --version
pdfinfo -v 2>&1 | head -1

cat <<'MSG'

Setup done. One step left, which needs you:
  run `source ~/.bashrc` (or open a new Ubuntu window) so the shell finds Node, then run
  `claude`, sign in with your Claude account (it shows a browser link), and type /exit.

Then run evals from the repo (its Windows path is under /mnt/c/...), as skills/job-search-assistant/evals/README.md shows.
MSG
