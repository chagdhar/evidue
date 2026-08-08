#!/usr/bin/env python3
"""Run backend pytest targets in isolated subprocesses.

By default every ``backend/tests/test_*.py`` file is run in its own process.
Optional positional pytest node ids are also supported. Process isolation keeps
leaked TestClient/server/thread state from contaminating later test modules and
ensures the outer proof process never inherits a child test process' output pipe.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "backend" / "tests"
DEFAULT_TIMEOUT_SECONDS = 120


def _tail(text: str, *, lines: int = 40) -> str:
    return "\n".join(text.splitlines()[-lines:])


def _signal_process_group(pid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return


def _run_target(target: str, *, timeout_seconds: int) -> tuple[bool, str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-q",
        "--tb=short",
    ]
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        timed_out = False
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _signal_process_group(process.pid, signal.SIGTERM)
            try:
                returncode = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _signal_process_group(process.pid, signal.SIGKILL)
                returncode = process.wait(timeout=5)
        finally:
            # If pytest exited while a child process survived, do not let that
            # child leak into the next target.
            _signal_process_group(process.pid, signal.SIGTERM)

        output.seek(0)
        text = output.read()
        if timed_out:
            return False, f"timed out after {timeout_seconds}s\n{_tail(text)}"
        return returncode == 0, text


def _default_targets() -> list[str]:
    return [str(path.relative_to(ROOT)) for path in sorted(TEST_ROOT.glob("test_*.py"))]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run backend pytest files/node ids in isolated subprocesses."
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="pytest file/node ids; defaults to every backend test file",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("EVIDUE_TEST_FILE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        help="timeout for each isolated pytest target (default: 120)",
    )
    args = parser.parse_args()

    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than zero")

    targets = args.targets or _default_targets()
    if not targets:
        print("No backend test targets found.", file=sys.stderr)
        return 2

    failures: list[tuple[str, str]] = []
    for index, target in enumerate(targets, 1):
        print(f"[RUN ] {index}/{len(targets)} {target}", flush=True)
        passed, output = _run_target(target, timeout_seconds=args.timeout_seconds)
        if passed:
            summary = next(
                (line for line in reversed(output.splitlines()) if "passed" in line),
                "passed",
            )
            print(f"[PASS] {target} — {summary}", flush=True)
        else:
            print(f"[FAIL] {target}", flush=True)
            print(_tail(output), flush=True)
            failures.append((target, output))

    print(flush=True)
    print(
        f"Backend test targets passed: {len(targets) - len(failures)}/{len(targets)}",
        flush=True,
    )
    if failures:
        print("Failed targets:")
        for target, _ in failures:
            print(f"- {target}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
