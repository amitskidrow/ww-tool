import os
import random
import signal
import sys
import time
from datetime import datetime


running = True
line_count = 0


def _handle_signal(signum, frame):  # noqa: ARG001
    global running
    running = False


def main() -> int:
    global line_count

    # Graceful shutdown on SIGTERM/SIGINT (systemd stop)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    name = os.path.splitext(os.path.basename(__file__))[0]
    interval = float(os.getenv("WW_LOG_INTERVAL", "1.0"))

    print(f"[{name}] starting up...", flush=True)
    while running:
        line_count += 1
        value = random.randint(0, 10_000)
        ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        print(
            f"ts={ts} component={name} line={line_count} number={value}",
            flush=True,
        )
        time.sleep(interval)

    print(f"[{name}] shutting down after line_count={line_count}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

