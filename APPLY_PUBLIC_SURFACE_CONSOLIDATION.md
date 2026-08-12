# Apply Evidue public-surface consolidation

This release removes the legacy public `/demo` application and folds its useful
inspection depth into `/try`. Because files are intentionally deleted, apply the
**full archive with `rsync --delete`** rather than using a simple tar overlay.

## 1. Confirm the current feature branch

```fish
cd ~/dev/evidue
git status
git branch -vv
```

The intended working branch is `feature/decision-ledger-v2`.

## 2. Extract the release outside the repo

```fish
rm -rf /tmp/evidue-public-surface
mkdir -p /tmp/evidue-public-surface

tar -xzf \
  ~/Downloads/evidue-public-surface-consolidation-2026-08-12.tgz \
  -C /tmp/evidue-public-surface
```

## 3. Synchronize it over the current checkout while preserving Git/dependencies

```fish
rsync -a --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='node_modules/' \
  --exclude='frontend/node_modules/' \
  --exclude='frontend/dist/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='test-results/' \
  --exclude='playwright-report/' \
  /tmp/evidue-public-surface/ \
  ~/dev/evidue/
```

## 4. Inspect and validate

```fish
cd ~/dev/evidue
git status --short
git diff --stat
git diff --check
./scripts/dev-check.sh full
```

## 5. Commit, consolidate branches, push, tag

Only after the full gate is green:

```fish
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "feat: consolidate public proof into Try Evidue"

git branch -vv
git branch --no-merged main

git switch main
git pull --ff-only origin main
git merge --ff-only feature/decision-ledger-v2

git branch --no-merged main
git branch -d feature/decision-ledger-v2

git push origin main

git tag -a baseline/validated-public-try-consolidation \
  -m "Validated Evidue public Try consolidation"
git push origin baseline/validated-public-try-consolidation

git fetch --all --prune --tags
git branch -vv
git branch -r -vv
git branch --no-merged main
git status
git log --oneline --decorate -8
```

The final product surface is intentionally only `/`, `/try`, `/contact`, and
`/workspace` (plus old `/pilot/*` compatibility redirects into `/workspace`).
