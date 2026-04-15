import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import lifespan
from app.api.router import api_router

logger = logging.getLogger("splitthetee")

API_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Split the Tee API",
        description="Golf Drinking Game Glass System",
        docs_url="/docs" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.FRONTEND_URL,
            "http://localhost:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        logger.info(
            "%s %s %d %.1fms",
            request.method, request.url.path, response.status_code, duration_ms,
        )
        return response

    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/status")
    async def status():
        """API status with version, DB status, and cache stats."""
        result = {
            "version": API_VERSION,
            "status": "ok",
            "mongodb": "unknown",
            "caches": {},
            "active_sessions": 0,
        }

        try:
            from app.core.database import get_collection
            db = get_collection("search_cache").database

            result["mongodb"] = "connected"

            # Cache stats
            for name in ("search_cache", "courses"):
                try:
                    count = await db[name].estimated_document_count()
                    result["caches"][name] = count
                except Exception:
                    result["caches"][name] = -1

            # Active game sessions
            try:
                result["active_sessions"] = await db["game_sessions"].count_documents(
                    {"active": True}
                )
            except Exception:
                pass
        except Exception:
            result["mongodb"] = "disconnected"

        return result

    @app.post("/api/v1/admin/cleanup")
    async def cleanup_caches():
        """Manually clear expired cache entries."""
        cleared = {}
        try:
            from app.core.database import get_collection
            from datetime import datetime, timezone, timedelta

            now = datetime.now(timezone.utc)

            # Search cache (7 day TTL)
            sc = get_collection("search_cache")
            r = await sc.delete_many(
                {"cached_at": {"$lt": now - timedelta(seconds=settings.SEARCH_CACHE_TTL)}}
            )
            cleared["search_cache"] = r.deleted_count

            # Courses cache (30 day TTL)
            cc = get_collection("courses")
            r = await cc.delete_many(
                {"cached_at": {"$lt": now - timedelta(seconds=settings.MAP_CACHE_TTL)}}
            )
            cleared["courses"] = r.deleted_count
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "cleared": cleared}

    return app


app = create_app()
