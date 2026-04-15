"""Per-hole bundled data — associates OSM features with holes."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.db.mongo import courses
from app.services.golf.holes import associate_features
from app.services.golf.osm import fetch_course_map

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/course-holes")
async def get_course_holes(
    courseId: str = Query(..., description="Golf API course ID"),
    lat: float | None = Query(None, description="Latitude fallback"),
    lng: float | None = Query(None, description="Longitude fallback"),
):
    """Get per-hole feature bundles for a course, cached by course_id."""
    collection = courses()

    # Check cache by course_id
    cached = await collection.find_one({"course_id": courseId})
    if cached and cached.get("holes"):
        return {
            "holes": cached["holes"],
            "course_name": cached.get("course_name"),
            "center": cached.get("center"),
            "font_hint": cached.get("font_hint"),
        }

    try:
        # Fetch course detail from Golf API
        course_data = None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{settings.GOLF_API_BASE}/courses/{courseId}",
                    headers={"Authorization": f"Key {settings.GOLF_API_KEY}"},
                )
                if response.is_success:
                    course_data = response.json()
                    if "course" in course_data:
                        course_data = course_data["course"]
        except Exception as exc:
            logger.warning("Could not fetch course detail: %s", exc)

        # Determine lat/lng from course data or fallback params
        course_lat = lat
        course_lng = lng
        if course_data:
            loc = course_data.get("location", {})
            if loc.get("latitude") and loc.get("longitude"):
                course_lat = loc["latitude"]
                course_lng = loc["longitude"]

        if course_lat is None or course_lng is None:
            raise HTTPException(
                status_code=400,
                detail="Could not determine course coordinates. Provide lat/lng params.",
            )

        # Fetch OSM features
        map_data = await fetch_course_map(course_lat, course_lng)

        # Associate features with holes
        holes = associate_features(map_data["features"], course_data)
        course_name = None
        if course_data:
            course_name = course_data.get("course_name") or course_data.get("club_name")

        from app.services.font_hints import get_font_hint
        font_hint = get_font_hint(course_name) if course_name else None

        result = {
            "holes": holes,
            "course_name": course_name,
            "center": map_data["center"],
            "font_hint": font_hint,
        }

        # Cache in courses collection
        if holes:
            doc = {
                "course_id": courseId,
                "course_name": course_name,
                "club_name": course_data.get("club_name") if course_data else None,
                "location": course_data.get("location") if course_data else {
                    "latitude": course_lat,
                    "longitude": course_lng,
                },
                "tees": course_data.get("tees") if course_data else None,
                "holes": holes,
                "osm_features": map_data["features"],
                "center": map_data["center"],
                "font_hint": font_hint,
                "cached_at": datetime.now(timezone.utc),
            }
            await collection.update_one(
                {"course_id": courseId},
                {"$set": doc},
                upsert=True,
            )

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Bundle error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to build course hole data")
