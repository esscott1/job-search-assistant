#!/usr/bin/env bash
# Approach A on the shared cases: the plugin's Tier 2 gold eval cases with the model pinned and
# each run's trace kept, then extract_a.py writes results/a.json. The cases run score.py, so this
# needs Linux, macOS or WSL (set up WSL first: docs/setup/windows-wsl-evals.md).
#   wsl -d Ubuntu -- bash /mnt/c/<path to repo>/orchestration/job-search/evals/comparison/run_a.sh
#   bash orchestration/job-search/evals/comparison/run_a.sh --runs 1
# The model is JOBS_MODEL, or claude-sonnet-5-5: the same default as approach B.
# Raw eval output and traces go to ~/eval-runs/comparison-<timestamp>, outside the repository.
set -uo pipefail

export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh" >/dev/null
fi
if ! command -v claude >/dev/null; then
  echo "claude not found. Set up WSL first: docs/setup/windows-wsl-evals.md" >&2
  exit 127
fi

runs=3
if [ "${1:-}" = "--runs" ]; then runs="$2"; fi
model="${JOBS_MODEL:-claude-sonnet-5-5}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../../.." && pwd)"
out="$HOME/eval-runs/comparison-$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$out"
echo "output dir: $out"

cd "$repo"
# --threshold 0: a run that fails a grader is still a result to compare, not a reason to stop.
claude plugin eval skills/job-search-assistant --case 'tier2-gold-*' --runs "$runs" \
  --ablation none --allow-tools Bash Write -j 3 --model "$model" --keep-temp \
  --threshold 0 --json "$out/result.json" --trust-plugin --no-publish --output-dir "$out"

# In the same session as the eval: WSL clears /tmp, where the traces are, when the distro stops.
python3 "$here/extract_a.py" "$out/result.json" --traces-dir "$out/traces" \
  --out "$here/results/a.json"
status=$?

# Remove the kept sandboxes; the traces are copied to $out/traces.
python3 -c "
import json, sys
for c in json.load(open(sys.argv[1]))['cases']:
    for r in c['arms']['with']:
        print('/'.join((r.get('tracePath') or '').split('/')[:3]))
" "$out/result.json" | sort -u | while read -r sandbox; do
  case "$sandbox" in
    /tmp/claude-eval-*) chmod -R u+rwx "$sandbox" 2>/dev/null; rm -rf "$sandbox" ;;
  esac
done
exit $status
