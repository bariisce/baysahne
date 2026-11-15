"""Notification worker: `python -m app.worker` (loop) or `python -m app.worker --once`.

Each tick: recover stuck jobs → cancel stale jobs → plan reminders → dispatch due jobs → check receipts.
Safe to run several instances (jobs are claimed with FOR UPDATE SKIP LOCKED) and safe to restart.
"""

import argparse
import logging
import signal
import time

from app.config import get_settings
from app.db import SessionLocal
from app.notifications import engine
from app.notifications.providers import get_provider

log = logging.getLogger("baysahne.worker")
_stop = False


def _handle(*_):
    global _stop
    _stop = True


def tick() -> dict:
    db = SessionLocal()
    try:
        return engine.run_once(db, get_provider())
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    args = parser.parse_args()
    s = get_settings()
    log.info("worker starting (env=%s, provider=%s, interval=%ss)", s.app_env, s.push_provider,
             s.worker_interval_seconds)
    if args.once:
        log.info("tick: %s", tick())
        return
    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    while not _stop:
        try:
            result = tick()
            if any(result.values()):
                log.info("tick: %s", result)
        except Exception:
            log.exception("worker tick failed; will retry next interval")
        for _ in range(s.worker_interval_seconds):
            if _stop:
                break
            time.sleep(1)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
