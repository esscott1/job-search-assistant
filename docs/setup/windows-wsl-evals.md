# Running evals on Windows with WSL

Some eval cases in this repo give Claude a shell: the Tier 2 scoring cases run `score.py`, and the resume cases run `render_resume.py` and `check_content.py`. `claude plugin eval` grants a shell only inside an OS sandbox, which exists on Linux and macOS but not on Windows. On Windows it refuses those runs.

The fix is WSL (Windows Subsystem for Linux): run the evals in Ubuntu on the same machine, against the same checkout. Cases that need no shell still run on Windows directly.

Setup takes about 15 minutes once. After that, a run is one command.

## 1. Install Ubuntu in WSL

In PowerShell **as Administrator**:

```powershell
wsl --install -d Ubuntu
```

Restart if asked. Ubuntu then opens and asks you to create a Linux username and password. You'll need that password for `sudo` in step 2.

From then on, open Ubuntu from any Command Prompt or PowerShell window with:

```powershell
wsl -d Ubuntu
```

Always name the distro. If Docker Desktop is installed, your *default* WSL distro may be `docker-desktop`, and a bare `wsl` opens that instead. `exit` returns to Windows.

## 2. Run the setup script

Your Windows drives are under `/mnt` in Ubuntu, so `C:\src\job-search-assistant` is `/mnt/c/src/job-search-assistant`. In Ubuntu:

```bash
cd /mnt/c/<path to your checkout>
bash scripts/setup-wsl-evals.sh
```

It asks for your Ubuntu password once, then installs:
- **bubblewrap and socat:** the sandbox Claude Code needs before it gives an eval run a shell.
- **python3-docx, LibreOffice, poppler-utils and the Carlito/Caladea fonts:** the resume builder's scripts.
- **python3-pytest:** to run the skills' unit tests inside Ubuntu.
- **Node.js 22 through nvm, and Claude Code**, at the version CI uses.

## 3. Sign in to Claude in Ubuntu

```bash
source ~/.bashrc
claude
```

Follow the browser link to sign in with your Claude account, then type `/exit`. The sign-in is saved in Ubuntu and survives restarts. Evals run on your own Claude login, so no API key is needed.

## 4. Run the evals

From the repo folder in Ubuntu:

```bash
bash scripts/run-evals-wsl.sh 'resume-*'              # every resume case, 3 runs each
bash scripts/run-evals-wsl.sh resume-history-rules --runs 1   # one case, one run
bash scripts/run-evals-wsl.sh                          # the whole suite
```

The first argument is a case glob, and anything after it is passed to `claude plugin eval`. The script runs with the plugin only (`--ablation none`), gives cases a shell (`--allow-tools Bash Write`), runs scaffold scripts (`--scaffold`, which the synced-folder cases need), and writes results to `~/eval-runs/<timestamp>`, outside the plugin. A run of all eight resume cases takes about 15 minutes and $12-13 of usage.

**Reading results.** A table at the end gives each case's score: 1.00 means every grader passed in every run. The full report is `report.html` in the output folder; from Windows, open `\\wsl$\Ubuntu\home\<your Linux username>\eval-runs\` in File Explorer. Add `--keep-temp` to keep each run's sandbox and `trace.jsonl` for debugging.

## Running evals from Claude Code on Windows

Claude Code running on Windows can drive the same evals through WSL, without you opening Ubuntu:

```powershell
wsl -d Ubuntu -- bash /mnt/c/<path to your checkout>/scripts/run-evals-wsl.sh 'resume-*'
```

What makes this work, and what to avoid:
- **Run a script file, not an inline command.** `wsl -d Ubuntu -- bash -c '…'` gets mangled. From Git Bash the paths are rewritten; from PowerShell, `$VARIABLES` are expanded on the Windows side before Ubuntu sees them.
- **`claude` isn't on the PATH in a non-interactive shell.** nvm loads from `~/.bashrc` only in an interactive shell, so `which claude` fails and Claude Code looks uninstalled when it isn't. `run-evals-wsl.sh` loads nvm itself.
- Unit tests run the same way: `wsl -d Ubuntu -- bash -c "cd /mnt/c/<path> && python3 -m pytest -q skills/"`. This command has no `$` variables, so PowerShell leaves it alone.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `wsl` opens `docker-desktop`, not Ubuntu | Use `wsl -d Ubuntu` |
| `claude: command not found` | `source ~/.bashrc` in Ubuntu, or use `run-evals-wsl.sh`, which loads nvm |
| The eval runner refuses to grant a shell | Run it in Ubuntu, not Windows; check `bwrap --version` works |
| Resume cases report "page count unverified" | Expected: LibreOffice can't start inside the eval sandbox. The page rules are covered by `test_render_resume.py`, which runs where LibreOffice is installed |
| `sudo` asks for a password Claude Code can't type | Run `scripts/setup-wsl-evals.sh` yourself in an Ubuntu window; the rest needs no `sudo` |
