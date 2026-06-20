#!/usr/bin/env python3
"""Boot smoke-test for the FROZEN backend.

Launches the PyInstaller-built backend executable and watches its stdout for the
newline-delimited JSON lifecycle events emitted by run.py. It is a pure boot
check — it does NOT load any model (inference spawns llama-server lazily, on the
first request). Success = the backend reaches `{"event": "ready"}` (embedded
PostgreSQL up + FastAPI lifespan complete). This is exactly the chain where the
mac packaging surfaced 7 freeze bugs; on Windows the risk is higher because
multiprocessing uses spawn (not fork).

Usage:
    python scripts/ci/smoke_boot.py <path-to-frozen-exe> [--port N]

Exit codes: 0 = booted (ready seen), 1 = startup_error / timeout / crash.
Env: SMOKE_TIMEOUT (seconds, default 240).
"""
import json
import os
import subprocess
import sys
import threading


def main() -> int:
    if len(sys.argv) < 2:
        print("SMOKE FAIL: missing path to frozen exe", flush=True)
        return 1
    exe = sys.argv[1]
    port = "8765"
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]
    timeout = int(os.environ.get("SMOKE_TIMEOUT", "240"))

    if not os.path.exists(exe):
        print(f"SMOKE FAIL: exe not found at {exe}", flush=True)
        return 1

    env = dict(os.environ)
    env.setdefault("ERUDI_FORCE_CPU", "1")  # no GPU on the runner — keep it explicit
    env.setdefault("PYTHONUNBUFFERED", "1")

    print(f"SMOKE: launching {exe} --port {port} (timeout {timeout}s)", flush=True)
    proc = subprocess.Popen(
        [exe, "--port", port],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # Watchdog: terminate the process after the timeout so the readline loop ends.
    timed_out = {"hit": False}

    def _kill_on_timeout():
        timed_out["hit"] = True
        proc.terminate()

    watchdog = threading.Timer(timeout, _kill_on_timeout)
    watchdog.start()

    ready = False
    failure = None
    try:
        for raw in proc.stdout:
            sys.stdout.write(raw)
            sys.stdout.flush()
            line = raw.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("event")
            if kind == "ready":
                ready = True
                break
            if kind == "startup_error":
                failure = f"startup_error: {event.get('code')} {event.get('message', '')}"
                break
    finally:
        watchdog.cancel()
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    if ready:
        print("SMOKE PASS: backend reached 'ready'", flush=True)
        return 0
    if timed_out["hit"]:
        print(f"SMOKE FAIL: timed out after {timeout}s without 'ready'", flush=True)
        return 1
    print(f"SMOKE FAIL: {failure or 'backend exited before ready'}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
