from collections import Counter

from app.config import settings
from app.extract import read_postgres, read_rqlite

# What one source hands to the load step: the warehouse table, the columns of
# its key and the rows to upsert into it.
Load = tuple[str, list[str], list[dict]]


def text(value) -> str | None:
    # Ids are uuid in Base, varchar in Crafting and TEXT in rqlite; as text they
    # can be joined across services in the warehouse.
    return None if value is None else str(value)


def flag(value) -> bool | None:
    # rqlite has no boolean type and stores 0 or 1.
    return None if value is None else bool(value)


def moment(value: str | None) -> str | None:
    # rqlite keeps times as text, which Postgres parses on insert; an unset time
    # can be stored as an empty string, which is not a valid timestamp.
    return value or None


def base() -> list[Load]:
    bases = read_postgres(
        "base",
        'SELECT "Id", "PlayerId", "DefenseScore", "StorageCapacity", "CreatedAtUtc" FROM "Bases"',
    )
    rewards = read_postgres(
        "base",
        'SELECT "Id", "BaseId", "RewardType", "GrantedToPlayerId", "GrantedAtUtc" '
        'FROM "KikiRewards"',
    )
    return [
        (
            "dim_base",
            ["base_id"],
            [
                {
                    "base_id": text(row["Id"]),
                    "player_id": text(row["PlayerId"]),
                    "defense_score": row["DefenseScore"],
                    "storage_capacity": row["StorageCapacity"],
                    "created_at": row["CreatedAtUtc"],
                }
                for row in bases
            ],
        ),
        (
            "fact_kiki_reward",
            ["reward_id"],
            [
                {
                    "reward_id": text(row["Id"]),
                    "base_id": text(row["BaseId"]),
                    "player_id": text(row["GrantedToPlayerId"]),
                    "reward_type": row["RewardType"],
                    "granted_at": row["GrantedAtUtc"],
                }
                for row in rewards
            ],
        ),
    ]


def crafting() -> list[Load]:
    recipes = read_postgres(
        "crafting",
        'SELECT "Id", "Name", "OutputItem", "OutputQuantity", "UnlockConditionType", '
        '"UnlockCourseId", "UnlockLevel", "CreatedAtUtc" FROM "Recipes"',
    )
    crafts = read_postgres(
        "crafting",
        'SELECT "Id", "PlayerId", "RecipeId", "ItemType", "Quantity", "CraftedAtUtc" '
        'FROM "CraftRecords"',
    )
    return [
        (
            "dim_recipe",
            ["recipe_id"],
            [
                {
                    "recipe_id": text(row["Id"]),
                    "name": row["Name"],
                    "output_item": row["OutputItem"],
                    "output_quantity": row["OutputQuantity"],
                    "unlock_condition_type": row["UnlockConditionType"],
                    "unlock_course_id": row["UnlockCourseId"],
                    "unlock_level": row["UnlockLevel"],
                    "created_at": row["CreatedAtUtc"],
                }
                for row in recipes
            ],
        ),
        (
            "fact_craft",
            ["craft_id"],
            [
                {
                    "craft_id": text(row["Id"]),
                    "player_id": text(row["PlayerId"]),
                    "recipe_id": text(row["RecipeId"]),
                    "item_type": row["ItemType"],
                    "quantity": row["Quantity"],
                    "crafted_at": row["CraftedAtUtc"],
                }
                for row in crafts
            ],
        ),
    ]


def zombie() -> list[Load]:
    types = read_postgres(
        "zombie",
        'SELECT "ZombieTypeId", "Name", "Category", "Health", "Speed", "AttackStrength", '
        '"PerceptionRadius", "Abilities", "Active" FROM zombie_types',
    )
    return [
        (
            "dim_zombie_type",
            ["zombie_type_id"],
            [
                {
                    "zombie_type_id": row["ZombieTypeId"],
                    "name": row["Name"],
                    "category": row["Category"],
                    "health": row["Health"],
                    "speed": row["Speed"],
                    "attack_strength": row["AttackStrength"],
                    "perception_radius": row["PerceptionRadius"],
                    "abilities": row["Abilities"],
                    "active": row["Active"],
                }
                for row in types
            ],
        ),
    ]


def resource() -> list[Load]:
    resources = read_postgres(
        "resource",
        'SELECT "PlayerId", "ResourceType", "Quantity" FROM player_resources',
    )
    return [
        (
            "snapshot_player_resource",
            ["player_id", "resource_type"],
            [
                {
                    "player_id": row["PlayerId"],
                    "resource_type": row["ResourceType"],
                    "quantity": row["Quantity"],
                }
                for row in resources
            ],
        ),
    ]


def game() -> list[Load]:
    url = settings().game_rqlite_url
    sessions = read_rqlite(
        url,
        "SELECT id, host_player_id, map_id, status, result, created_at, ended_at FROM sessions",
    )
    # The warehouse keeps how many players a session had, not who they were.
    players = Counter(
        row["session_id"] for row in read_rqlite(url, "SELECT session_id FROM session_players")
    )
    return [
        (
            "fact_game_session",
            ["session_id"],
            [
                {
                    "session_id": row["id"],
                    "host_player_id": row["host_player_id"],
                    "map_id": row["map_id"],
                    "status": row["status"],
                    "result": row["result"],
                    "player_count": players[row["id"]],
                    "created_at": moment(row["created_at"]),
                    "ended_at": moment(row["ended_at"]),
                }
                for row in sessions
            ],
        ),
    ]


def player() -> list[Load]:
    # email and password are never selected: the warehouse is for analysis and
    # needs neither, and every copy of a password is one more place to leak it.
    players = read_rqlite(
        settings().player_rqlite_url,
        "SELECT id, username, xp, level, online_status FROM players",
    )
    return [
        (
            "dim_player",
            ["player_id"],
            [
                {
                    "player_id": row["id"],
                    "username": row["username"],
                    "xp": row["xp"],
                    "level": row["level"],
                    "online_status": row["online_status"],
                }
                for row in players
            ],
        ),
    ]


def exam() -> list[Load]:
    url = settings().exam_rqlite_url
    courses = read_rqlite(
        url,
        "SELECT course_id, name, time_limit_seconds, pass_threshold, max_attempts FROM courses",
    )
    attempts = read_rqlite(
        url,
        "SELECT attempt_id, player_id, game_session_id, course_id, status, started_at, "
        "submitted_at, score, correct_answers, passed FROM attempts",
    )
    return [
        ("dim_course", ["course_id"], courses),
        (
            "fact_exam_attempt",
            ["attempt_id"],
            [
                {
                    **row,
                    "started_at": moment(row["started_at"]),
                    "submitted_at": moment(row["submitted_at"]),
                    "passed": flag(row["passed"]),
                }
                for row in attempts
            ],
        ),
    ]


def world() -> list[Load]:
    url = settings().world_rqlite_url
    rooms = read_rqlite(url, "SELECT room_id, world_id, section_id, name, type, floor FROM rooms")
    # Each room carries its section's name and state, so a query on the
    # warehouse needs no join to know whether a room is unlocked.
    sections = {
        row["section_id"]: row
        for row in read_rqlite(url, "SELECT section_id, name, unlocked FROM sections")
    }
    return [
        (
            "dim_world_room",
            ["room_id"],
            [
                {
                    "room_id": row["room_id"],
                    "world_id": row["world_id"],
                    "section_id": row["section_id"],
                    "section_name": sections.get(row["section_id"], {}).get("name"),
                    "section_unlocked": flag(sections.get(row["section_id"], {}).get("unlocked")),
                    "room_name": row["name"],
                    "room_type": row["type"],
                    "floor": row["floor"],
                }
                for row in rooms
            ],
        ),
    ]


# Every source the ETL reads, by the name it is recorded under in etl.runs.
SOURCES = {
    "base": base,
    "crafting": crafting,
    "zombie": zombie,
    "resource": resource,
    "game": game,
    "player": player,
    "exam": exam,
    "world": world,
}
