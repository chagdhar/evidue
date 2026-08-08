# Apply the Evidue verification-kernel leap

This archive intentionally does not contain `.git` history. Apply it over your existing Evidue checkout on a new branch.

```fish
cd /home/dharun/dev/evidue
git switch -c feature/verification-kernel-leap

mkdir -p /tmp/evidue-next-leap
tar -xzf /path/to/evidue-next-leap-2026-08-08.tgz -C /tmp/evidue-next-leap

rsync -a \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='.venv' \
  --exclude='node_modules' \
  /tmp/evidue-next-leap/evidue/ \
  /home/dharun/dev/evidue/
```

Then run the offline proof first:

```fish
cd /home/dharun/dev/evidue
./scripts/evidue-proof.sh core
```

Run the normal repository gates in the bootstrapped checkout:

```fish
uv run ruff format --check backend scripts
uv run ruff check backend scripts
uv run pytest backend/tests -q
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

For a pinned live Gemini qualification (server/developer credential, never customer BYOK):

```fish
set -x EVIDUE_LLM_PRIMARY gemini
set -x GEMINI_MODEL gemini-3.6-flash
set -x GEMINI_API_KEY 'YOUR_SERVER_KEY'
./scripts/evidue-proof.sh live --provider gemini --model "$GEMINI_MODEL"
```

For OpenAI, configure `OPENAI_API_KEY` and an `OPENAI_MODEL` enabled for the deployment, then run the same `live` command with `--provider openai --model "$OPENAI_MODEL"`.

Do not cite the old SEC live smoke result. The previous downloaded `.html` contained gzip transport bytes; this archive repairs the artifact and requires a new live qualification.
