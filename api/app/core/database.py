from __future__ import annotations

from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.core.config import settings

_db: AsyncIOMotorDatabase | None = None


def get_collection(name: str):
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db[name]


async def _ensure_indexes() -> None:
    """Create indexes for all collections."""

    # Search cache — TTL index
    search_cache = _db["search_cache"]
    await search_cache.create_index([("query", ASCENDING)], unique=True)
    await search_cache.create_index(
        [("cached_at", ASCENDING)],
        expireAfterSeconds=settings.SEARCH_CACHE_TTL,
    )

    # Courses — keyed by course_id, with TTL
    courses = _db["courses"]
    await courses.create_index([("course_id", ASCENDING)], unique=True)
    await courses.create_index(
        [("cached_at", ASCENDING)],
        expireAfterSeconds=settings.MAP_CACHE_TTL,
    )

    # Glass sets
    glass_sets = _db["glass_sets"]
    await glass_sets.create_index([("created_at", DESCENDING)])

    # Game sessions
    game_sessions = _db["game_sessions"]
    await game_sessions.create_index([("glass_set_id", ASCENDING)])
    await game_sessions.create_index([("created_at", DESCENDING)])

    # Players
    players = _db["players"]
    await players.create_index([("session_id", ASCENDING)])

    # Scores
    scores = _db["scores"]
    await scores.create_index(
        [("session_id", ASCENDING), ("player_id", ASCENDING), ("hole_number", ASCENDING)]
    )

    # Settings
    design_settings = _db["design_settings"]
    await design_settings.create_index([("created_at", DESCENDING)])

    # Preorders — unique on lowercased email
    preorders = _db["preorders"]
    await preorders.create_index([("email", ASCENDING)], unique=True)
    await preorders.create_index([("created_at", DESCENDING)])


@asynccontextmanager
async def lifespan(app):
    global _db
    client_kwargs: dict = {}
    if settings.MONGODB_AUTH_MECHANISM == "MONGODB-AWS":
        client_kwargs["authMechanism"] = "MONGODB-AWS"
        client_kwargs["authSource"] = "$external"
    client = AsyncIOMotorClient(settings.MONGODB_URI, **client_kwargs)
    _db = client[settings.MONGODB_DB_NAME]
    app.state.db = _db
    try:
        await _ensure_indexes()
    except Exception as exc:
        import logging
        logging.getLogger("splitthetee").warning("Index creation failed (may need DB permissions): %s", exc)
    yield
    _db = None
    client.close()
