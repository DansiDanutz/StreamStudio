"""Schema migrations: the API and every worker thread migrate at start-up, at the same time."""

import threading

from streamstudio.core import db


def test_concurrent_migrations_apply_each_step_once(tmp_path):
    path = tmp_path / "s.db"
    errors: list[BaseException] = []
    start = threading.Barrier(6)

    def run() -> None:
        start.wait(timeout=10)
        try:
            conn = db.connect(path)
            db.migrate(conn)
            conn.close()
        except BaseException as e:  # noqa: BLE001 — collected for the assertion
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == []
    conn = db.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)


def test_migrate_is_a_no_op_when_current(tmp_path):
    conn = db.connect(tmp_path / "s.db")
    assert db.migrate(conn) == len(db.MIGRATIONS)
    assert db.migrate(conn) == len(db.MIGRATIONS)
