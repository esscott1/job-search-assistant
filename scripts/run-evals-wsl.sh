#!/usr/bin/env bash
# Run a plugin's eval cases inside WSL Ubuntu (or any Linux), including the cases that need a shell.
# Works from a non-interactive shell, so Claude Code on Windows can run it too:
#   wsl -d Ubuntu -- bash /mnt/c/<path to repo>/scripts/run-evals-wsl.sh 'resume-*'
# From an Ubuntu terminal, inside the repo:
#   bash scripts/run-evals-wsl.sh 'resume-*' --runs 1
#
# Arguments: a case glob (default: every case; one pattern, no {a,b} braces), then any extra
# `claude plugin eval` options, which override the defaults below. Set EVAL_PLUGIN to evaluate
# another category (default: skills/job-search-assistant).
# Results go to ~/eval-runs/<timestamp>, outside the plugin, as the evals README requires.
# Set up WSL first: docs/setup/windows-wsl-evals.md.
set -uo pipefail

# Claude Code is installed through nvm, which normally loads only in an interactive shell.
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh" >/dev/null
fi
if ! command -v claude >/dev/null; then
  echo "claude not found. Set up WSL first: docs/setup/windows-wsl-evals.md" >&2
  exit 127
fi

cd "$(dirname "$0")/.."
case_glob="${1:-*}"
shift || true
out="$HOME/eval-runs/$(date +%Y%m%d-%H%M%S)-$$"
echo "output dir: $out"
claude plugin eval "${EVAL_PLUGIN:-skills/job-search-assistant}" --case "$case_glob" \
  --runs 3 --ablation none --allow-tools Bash Write -j 3 --scaffold \
  --trust-plugin --no-publish --output-dir "$out" "$@"
