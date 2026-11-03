"""Worker process: claims queued jobs from SQLite and runs their handlers.

Run with `streamstudio-worker`. Multiple worker processes may run at once; claims are
transactional, and jobs whose worker stops heartbeating are requeued.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
import traceback

from ..core import db, store
from ..core.config import Settings, get_settings
from ..episode import handlers as _episode_handlers  # noqa: F401  (registers the episode handlers)
from .handlers import HANDLERS, JobContext

log = logging.getLogger("streamstudio.worker")


def run_one(conn, settings: Settings, worker_id: str) -> bool:
    """Claim and run a single job. Returns False if the queue was empty."""
    job = store.claim_job(conn, worker_id)
    if job is None:
        return False
    fn = HANDLERS.get(job["kind"])
    log.info("job %s (%s) started", job["id"], job["kind"])
    if fn is None:
        store.fail_job(conn, job["id"], f"no handler for kind '{job['kind']}'", max_attempts=0)
        return True

    stop = threading.Event()

    def beat() -> None:  # keep the heartbeat fresh while long ffmpeg calls run
        hb = db.connect(settings.db_path)
        while not stop.wait(15):
            store.heartbeat(hb, job["id"])
        hb.close()

    t = threading.Thread(target=beat, daemon=True)
    t.start()
    try:
        result = fn(JobContext(job=job, conn=conn, settings=settings))
        current = store.get_job(conn, job["id"])
        if current and current["status"] == "cancelled":
            log.info("job %s cancelled", job["id"])
        else:
            store.finish_job(conn, job["id"], result)
            log.info("job %s done", job["id"])
    except Exception as e:  # noqa: BLE001 — every failure is recorded on the job
        payload = job.get("payload") or {}
        max_attempts = payload.get("max_attempts") if isinstance(payload, dict) else None
        status = store.fail_job(
            conn, job["id"], f"{e}\n{traceback.format_exc()}",
            int(max_attempts) if max_attempts else settings.job_max_attempts,
        )  # fmt: skip
        log.warning("job %s failed (%s): %s", job["id"], status, e)
        episode_id = payload.get("episode_id") if isinstance(payload, dict) else None
        if status == "error" and episode_id and job["kind"] != "episode_advance":
            # the planner decides what a failed stage means; it never re-renders on its own
            store.enqueue(
                conn, "episode_advance", project_id=job.get("project_id"),
                payload={"episode_id": episode_id},
            )  # fmt: skip
    finally:
        stop.set()
    return True


def loop(settings: Settings, worker_id: str, stop: threading.Event, poll_s: float = 0.5) -> None:
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    last_sweep = 0.0
    while not stop.is_set():
        if time.time() - last_sweep > 30:
            n = store.requeue_stale(conn, settings.job_heartbeat_timeout_s)
            if n:
                log.warning("requeued %d stale job(s)", n)
            last_sweep = time.time()
        if not run_one(conn, settings, worker_id):
            stop.wait(poll_s)
    conn.close()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    base = f"{socket.gethostname()}:{os.getpid()}"
    threads = [
        threading.Thread(target=loop, args=(settings, f"{base}:{i}", stop), daemon=True)
        for i in range(settings.worker_concurrency)
    ]
    for t in threads:
        t.start()
    log.info("worker up: %d slot(s), data=%s", len(threads), settings.data_dir)
    while not stop.is_set():
        stop.wait(1)
    for t in threads:
        t.join(timeout=5)


if __name__ == "__main__":
    run()
