# Handoff

Fresh checkout: run `./scripts/bootstrap.sh`; seed with `./scripts/seed-demo.sh`;
start development with `./scripts/dev.sh`; open `http://localhost:5173/demo`.
Run `./scripts/dev-check.sh full` before handoff. Container: `docker build -t
evidue-demo .` then `docker run -p 8000:8000 evidue-demo`.
