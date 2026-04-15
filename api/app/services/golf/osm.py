"""OpenStreetMap / Overpass API service — fetch and parse course features."""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def query_overpass(query: str) -> dict | None:
    """Query Overpass API with retry logic across multiple endpoints."""
    for endpoint in settings.OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        endpoint,
                        data={"data": query},
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )

                if response.status_code in (429, 504):
                    if attempt == 0:
                        await asyncio.sleep(2)
                        continue
                    break

                if not response.is_success:
                    break

                text = response.text
                if text.lstrip().startswith("<"):
                    logger.warning("Overpass %s returned HTML (busy), trying next...", endpoint)
                    break

                return response.json()
            except Exception as exc:
                logger.warning("Overpass %s attempt %d failed: %s", endpoint, attempt + 1, exc)
                if attempt == 0:
                    continue
                break
    return None


def _determine_category(tags: dict) -> str | None:
    """Map OSM tags to a feature category."""
    golf = tags.get("golf")
    leisure = tags.get("leisure")
    natural = tags.get("natural")
    water = tags.get("water")

    if golf == "fairway":
        return "fairway"
    if golf == "green":
        return "green"
    if golf == "tee":
        return "tee"
    if golf == "bunker":
        return "bunker"
    if golf == "rough":
        return "rough"
    if golf == "hole":
        return "hole"
    if golf in ("cartpath", "path"):
        return "path"
    if golf == "driving_range":
        return "fairway"
    if natural == "water" or water:
        return "water"
    if leisure == "golf_course":
        return "course_boundary"
    return None


def parse_overpass_features(raw: dict) -> list[dict]:
    """Convert raw Overpass response elements into feature dicts."""
    nodes: dict[int, list[float]] = {}
    for el in raw.get("elements", []):
        if el.get("type") == "node":
            nodes[el["id"]] = [el["lat"], el["lon"]]

    features = []
    for el in raw.get("elements", []):
        if el.get("type") != "way" or not el.get("tags"):
            continue

        coords = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
        if len(coords) < 2:
            continue

        category = _determine_category(el["tags"])
        if category is None:
            continue

        par_str = el["tags"].get("par")
        features.append({
            "id": str(el["id"]),
            "category": category,
            "ref": el["tags"].get("ref"),
            "par": int(par_str) if par_str else None,
            "name": el["tags"].get("name"),
            "coords": coords,
        })

    return features


async def fetch_course_map(lat: float, lng: float, radius: int = 2000) -> dict:
    """Fetch course map features from OSM.

    Returns dict with 'features' and 'center' keys.
    """
    radius = min(radius, 3000)

    query = f"""[out:json][timeout:30];
(
  way["golf"](around:{radius},{lat},{lng});
  relation["golf"](around:{radius},{lat},{lng});
  way["natural"="water"](around:{radius},{lat},{lng});
  relation["natural"="water"](around:{radius},{lat},{lng});
  way["water"](around:{radius},{lat},{lng});
  relation["water"](around:{radius},{lat},{lng});
  way["leisure"="golf_course"](around:{radius},{lat},{lng});
  relation["leisure"="golf_course"](around:{radius},{lat},{lng});
);
out body;
>;
out skel qt;"""

    raw = await query_overpass(query)
    if raw is None:
        return {"features": [], "center": [lat, lng]}

    features = parse_overpass_features(raw)
    return {"features": features, "center": [lat, lng]}
