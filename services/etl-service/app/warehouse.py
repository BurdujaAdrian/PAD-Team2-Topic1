import psycopg
from psycopg import sql

from app.config import settings

# Created on every start; IF NOT EXISTS makes a restart a no-op. Every table keys
# on the id it has in its source, so loading the same row twice updates it
# instead of adding a duplicate.
SCHEMA = """
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS etl;

CREATE TABLE IF NOT EXISTS dw.dim_player (
    player_id     TEXT PRIMARY KEY,
    username      TEXT,
    xp            INTEGER,
    level         INTEGER,
    online_status TEXT,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.dim_recipe (
    recipe_id             TEXT PRIMARY KEY,
    name                  TEXT,
    output_item           TEXT,
    output_quantity       INTEGER,
    unlock_condition_type TEXT,
    unlock_course_id      TEXT,
    unlock_level          INTEGER,
    created_at            TIMESTAMPTZ,
    loaded_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.dim_course (
    course_id          TEXT PRIMARY KEY,
    name               TEXT,
    time_limit_seconds INTEGER,
    pass_threshold     DOUBLE PRECISION,
    max_attempts       INTEGER,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.dim_zombie_type (
    zombie_type_id    TEXT PRIMARY KEY,
    name              TEXT,
    category          TEXT,
    health            INTEGER,
    speed             DOUBLE PRECISION,
    attack_strength   INTEGER,
    perception_radius INTEGER,
    abilities         TEXT[],
    active            BOOLEAN,
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.dim_world_room (
    room_id          TEXT PRIMARY KEY,
    world_id         TEXT,
    section_id       TEXT,
    section_name     TEXT,
    section_unlocked BOOLEAN,
    room_name        TEXT,
    room_type        TEXT,
    floor            INTEGER,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.dim_base (
    base_id          TEXT PRIMARY KEY,
    player_id        TEXT,
    defense_score    INTEGER,
    storage_capacity INTEGER,
    created_at       TIMESTAMPTZ,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.fact_craft (
    craft_id   TEXT PRIMARY KEY,
    player_id  TEXT,
    recipe_id  TEXT,
    item_type  TEXT,
    quantity   INTEGER,
    crafted_at TIMESTAMPTZ,
    loaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.fact_kiki_reward (
    reward_id   TEXT PRIMARY KEY,
    base_id     TEXT,
    player_id   TEXT,
    reward_type TEXT,
    granted_at  TIMESTAMPTZ,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.fact_exam_attempt (
    attempt_id      TEXT PRIMARY KEY,
    player_id       TEXT,
    game_session_id TEXT,
    course_id       TEXT,
    status          TEXT,
    started_at      TIMESTAMPTZ,
    submitted_at    TIMESTAMPTZ,
    score           DOUBLE PRECISION,
    correct_answers INTEGER,
    passed          BOOLEAN,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.fact_game_session (
    session_id     TEXT PRIMARY KEY,
    host_player_id TEXT,
    map_id         TEXT,
    status         TEXT,
    result         TEXT,
    player_count   INTEGER,
    created_at     TIMESTAMPTZ,
    ended_at       TIMESTAMPTZ,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dw.snapshot_player_resource (
    player_id     TEXT,
    resource_type TEXT,
    quantity      INTEGER,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, resource_type)
);

CREATE TABLE IF NOT EXISTS etl.runs (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT NOT NULL,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(settings().postgres_dsn("warehouse"), connect_timeout=5)


def init_warehouse() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


def upsert(conn: psycopg.Connection, table: str, key: list[str], rows: list[dict]) -> int:
    if not rows:
        return 0
    columns = list(rows[0])
    updates = [column for column in columns if column not in key]
    # Table and column names cannot be query parameters; sql.Identifier quotes
    # them, so a name can never be read as SQL.
    query = sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({values}) "
        "ON CONFLICT ({key}) DO UPDATE SET {updates}, loaded_at = now()"
    ).format(
        table=sql.Identifier("dw", table),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join(sql.Placeholder(column) for column in columns),
        key=sql.SQL(", ").join(map(sql.Identifier, key)),
        updates=sql.SQL(", ").join(
            sql.SQL("{column} = EXCLUDED.{column}").format(column=sql.Identifier(column))
            for column in updates
        ),
    )
    with conn.cursor() as cur:
        cur.executemany(query, rows)
    return len(rows)


def record_run(
    conn: psycopg.Connection,
    source: str,
    started_at,
    status: str,
    rows_loaded: int = 0,
    error: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO etl.runs (source, started_at, status, rows_loaded, error) "
        "VALUES (%s, %s, %s, %s, %s)",
        (source, started_at, status, rows_loaded, error),
    )
