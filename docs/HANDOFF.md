# Handoff

## Fresh checkout

Requirements: Git, Python 3.13 or newer, uv, Node 20.19 or newer, npm, and
Docker. Commands below are directly invokable from fish.

```fish
git clone <repository-url> evidue
cd evidue
./scripts/bootstrap.sh
./scripts/seed-demo.sh
./scripts/dev-check.sh full
./scripts/dev.sh
```

Open <http://localhost:5173/demo>. Stop both development processes with
`Ctrl+C`; `dev.sh` terminates its child processes.

`/demo` is fixed to the full 10,000-line headline invoice and is the recording
route. Open <http://localhost:5173/demo/lab> only for the focused contradictory
evidence, recovery, and duplicate-attribution cases.

## Demo reset

With development servers stopped:

```fish
./scripts/demo-reset.sh
```

The script recreates the deterministic inputs and returns the application to the
unreconciled state.

## Container

```fish
docker build -t evidue-demo .
docker run --rm -p 8000:8000 evidue-demo
```

Open <http://localhost:8000/demo>. The image serves the built React assets
through FastAPI and runs as the unprivileged `evidue` user.
