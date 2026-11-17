import httpx
import psycopg
from psycopg.rows import dict_row

from app.config import settings

# A source that does not answer within this time fails its own part of the run
# instead of holding up the other sources.
TIMEOUT_SECONDS = 5


class ExtractError(Exception):
    """A source could not be read; the run marks that source as failed."""


def read_postgres(name: str, query: str) -> list[dict]:
    try:
        with psycopg.connect(
            settings().postgres_dsn(name),
            connect_timeout=TIMEOUT_SECONDS,
            row_factory=dict_row,
        ) as conn:
            # The ETL only reads from the service databases; a read-only
            # transaction makes Postgres refuse any write, even a buggy one.
            conn.read_only = True
            return conn.execute(query).fetchall()
    except psycopg.Error as exc:
        raise ExtractError(f"{name}: {exc}") from exc


def read_rqlite(url: str, query: str) -> list[dict]:
    try:
        # /db/query only runs reads; writes would need /db/execute.
        response = httpx.post(f"{url}/db/query", json=[query], timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExtractError(f"{url}: {exc}") from exc
    result = response.json()["results"][0]
    # A bad query still answers 200; the error is inside the result.
    if "error" in result:
        raise ExtractError(f"{url}: {result['error']}")
    columns = result["columns"]
    # rqlite leaves "values" out when the table is empty.
    return [dict(zip(columns, row, strict=True)) for row in result.get("values", [])]
