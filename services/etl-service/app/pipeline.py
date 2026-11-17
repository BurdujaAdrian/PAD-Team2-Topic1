import logging
import threading
from datetime import UTC, datetime

import psycopg

from app.transform import SOURCES
from app.warehouse import connect, record_run, upsert

logger = logging.getLogger("etl")

# The periodic run and one started by POST /run would load the same rows at the
# same time; the second one waits for the first to finish.
_lock = threading.Lock()


def run_source(name: str, source) -> dict:
    started_at = datetime.now(UTC)
    try:
        loads = source()
        # One transaction per source: if any of its tables fails to load, none
        # of them changes, and the warehouse never holds half a source.
        with connect() as conn:
            rows_loaded = sum(upsert(conn, table, key, rows) for table, key, rows in loads)
            record_run(conn, name, started_at, "ok", rows_loaded)
    # Any error, not only a database that is down: a bug in one source's
    # transform must not stop the other sources from loading.
    except Exception as exc:
        logger.warning("etl_source_failed source=%s error=%s", name, exc)
        try:
            with connect() as conn:
                record_run(conn, name, started_at, "failed", error=str(exc))
        except psycopg.Error:
            # The warehouse itself is down; the log line above is all that is left.
            pass
        return {"source": name, "status": "failed", "rows_loaded": 0, "error": str(exc)}
    logger.info("etl_source_loaded source=%s rows=%s", name, rows_loaded)
    return {"source": name, "status": "ok", "rows_loaded": rows_loaded, "error": None}


def run_all() -> list[dict]:
    with _lock:
        return [run_source(name, source) for name, source in SOURCES.items()]
