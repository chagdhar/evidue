# Apply Decision Ledger V2

This release is designed to overlay the current validated Evidue checkout. It intentionally leaves backend financial logic unchanged.

## 1. Start from canonical `main`

```fish
cd ~/dev/evidue
git status
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feature/decision-ledger-v2
```

## 2. Apply the overlay

```fish
tar -xzf ~/Downloads/evidue-decision-ledger-v2-overlay-2026-08-12.tgz -C ~/dev/evidue
```

## 3. Inspect before testing

```fish
git status --short
git diff --stat
git diff --check
```

## 4. Run the full release gate

```fish
./scripts/dev-check.sh full
```

## 5. Commit only after the full gate is green

```fish
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "feat: introduce Evidue decision ledger design v2"
```

## 6. Inspect and merge every intended open branch

```fish
git branch -vv
git branch --no-merged main
```

If `feature/decision-ledger-v2` is the only intended unmerged branch:

```fish
git switch main
git pull --ff-only origin main
git merge --ff-only feature/decision-ledger-v2
git branch --no-merged main
git branch -d feature/decision-ledger-v2
git push origin main
```

## 7. Tag the validated canonical state

```fish
git tag -a baseline/validated-decision-ledger-v2 -m "Validated Evidue Decision Ledger V2"
git push origin baseline/validated-decision-ledger-v2
```

## 8. Final canonical verification

```fish
git fetch --all --prune --tags
git branch -vv
git branch -r -vv
git branch --no-merged main
git status
git log --oneline --decorate -8
```

The desired result is a clean `main`, synchronized `origin/main`, no intended unmerged branches, and `baseline/validated-decision-ledger-v2` pointing at the V2 commit.
