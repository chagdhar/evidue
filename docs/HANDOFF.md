# Handoff

## Fresh checkout

Requirements: Git, Python 3.13+, uv, Node 20.19+, npm, and Docker.

```fish
git clone <repository-url> evidue
cd evidue
./scripts/bootstrap.sh
./scripts/seed-demo.sh
./scripts/dev-check.sh full
./scripts/dev.sh
```

Open <http://localhost:5173/try> for the public proof and <http://localhost:5173/workspace> for the protected product.

The public proof uses deterministic synthetic fixtures and cannot mutate protected workspace state. The useful inspection features that previously lived in a separate public reference shell—claim audit trail, source-record provenance, outcome receipt, reproducibility metadata, and dispute-summary handoff—now appear inline in `/try`.

## Reset synthetic fixtures

With development servers stopped:

```fish
./scripts/demo-reset.sh
```

This resets the internal synthetic fixture database used by `/try`; it does not affect protected workspace data.

## Container

```fish
docker build -t evidue .
docker run --rm -p 8000:8000 evidue
```

Open <http://localhost:8000/try>.
