# Evidue

Deterministic reconciliation demo for Acme Commerce's synthetic Nova Support AI
invoice. Start with `./scripts/bootstrap.sh`, then `./scripts/dev.sh` and open
http://localhost:5173/demo. Production-style serving: `docker build -t
evidue-demo . && docker run -p 8000:8000 evidue-demo`, then open `/demo`.
