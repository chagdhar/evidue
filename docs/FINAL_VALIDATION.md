# Final validation

This document is updated only with commands actually run.

`./scripts/dev-check.sh full` passed on 2026-07-27: Ruff passed; pytest passed
3 tests; ESLint passed; Vite production build passed. `docker build -t
evidue-demo .` was attempted twice. Both attempts fetched the Node base image
and reached `npm install`; the execution environment ended the build before an
image was produced, so container runtime and clean-checkout validation have not
been claimed.
