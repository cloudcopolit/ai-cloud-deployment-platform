"""Worker process: `python -m app.jobs.worker`. Claims QUEUED jobs one at a time, sweeps
stale ones, and stops cleanly on SIGTERM/SIGINT (the current job finishes first)."""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
import uuid

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.integrations.github_app import get_github_client
from app.jobs.queue import claim_next, sweep
from app.jobs.runner import execute

logger = logging.getLogger("cloudpilot.worker")
SWEEP_EVERY_S = 15


def worker_id() -> str:
    return f"{socket.gethostname()[:30]}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def run(stop: threading.Event, *, once: bool = False) -> int:
    """Main loop. With once=True, processes at most one job (used by tests). Returns jobs run."""
    me = worker_id()
    github = get_github_client()
    last_sweep = 0.0
    processed = 0
    logger.info("worker_started", extra={"context": {"worker_id": me}})
    while not stop.is_set():
        if time.monotonic() - last_sweep >= SWEEP_EVERY_S:
            with SessionLocal() as db:
                swept = sweep(db)
            if swept.requeued or swept.timed_out or swept.cancelled:
                logger.info("sweep", extra={"context": swept.__dict__})
            last_sweep = time.monotonic()
        with SessionLocal() as db:
            job_id = claim_next(db, me)
        if job_id is None:
            if once:
                break
            stop.wait(settings.worker_poll_interval_s)
            continue
        logger.info("job_claimed", extra={"context": {"job_id": str(job_id), "worker_id": me}})
        try:
            execute(job_id, me, session_factory=SessionLocal, github=github)
        except Exception:
            # Never crash the loop on one job; the sweeper will recover it if needed.
            logger.exception("job_crashed", extra={"context": {"job_id": str(job_id)}})
        processed += 1
        if once:
            break
    logger.info("worker_stopped", extra={"context": {"worker_id": me}})
    return processed


def main() -> None:  # pragma: no cover - process entry point
    configure_logging()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    run(stop)


if __name__ == "__main__":  # pragma: no cover
    main()
