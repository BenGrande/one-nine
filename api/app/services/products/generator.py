"""Shared helpers that turn a course record into product-page artifacts.

Two callers rely on this module:
- `scripts/generate_products.py` (build-time), which writes the per-course JSON
  + assets consumed by the SSG prerender.
- `GET /api/v1/products` + `/products/{slug}` (runtime), which read from Mongo.

Keeping the logic here avoids the two paths drifting.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from app.services.render.glass_template import compute_glass_template, warp_layout
from app.services.render.layout import compute_layout, split_into_glasses
from app.services.render.scoring import (
    add_scoring_features_to_layout,
    compute_all_scoring_zones,
    compute_all_terrain_following_zones,
)
from app.services.render.svg import render_svg


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Slugify arbitrary text: ascii-fold, lowercase, kebab-case, trim dashes."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    slug = _SLUG_RE.sub("-", lowered).strip("-")
    return slug


def slugify_course(course: dict) -> str:
    """Slug = course-name + city + state, e.g. `pebble-beach-golf-links-pebble-beach-ca`."""
    name = course.get("name") or course.get("club_name") or ""
    loc = course.get("location") or {}
    parts = [name, loc.get("city"), loc.get("state")]
    return slugify("-".join(p for p in parts if p))


def default_tee(course: dict) -> dict | None:
    """Pick a representative tee (men's white if present; else first)."""
    tees = course.get("tees") or []
    if not tees:
        return None
    preferred = [
        t for t in tees
        if (t.get("gender") == "mens" or t.get("gender") == "male")
        and "white" in (t.get("tee_name") or "").lower()
    ]
    if preferred:
        return preferred[0]
    return tees[0]


def compute_stats(course: dict) -> dict:
    """Derive high-level stats from a course record."""
    tee = default_tee(course) or {}
    tee_holes = tee.get("holes") or course.get("holes") or []
    total_par = sum((h.get("par") or 0) for h in tee_holes)
    total_yardage = sum((h.get("yardage") or 0) for h in tee_holes)

    # Signature hole = hole with lowest handicap number (hardest).
    signature_hole = None
    if tee_holes:
        with_handicap = [h for h in tee_holes if h.get("handicap")]
        if with_handicap:
            signature_hole = min(with_handicap, key=lambda h: h["handicap"]).get("number")

    hole_count = len(tee_holes)
    est_round_minutes = 12 * hole_count if hole_count else None

    return {
        "total_par": total_par,
        "total_yardage": total_yardage,
        "tee_count": len(course.get("tees") or []),
        "holes": hole_count,
        "signature_hole": signature_hole,
        "est_round_minutes": est_round_minutes,
    }


def build_glass3d(course: dict, glass_number: int = 1, glass_count: int = 2) -> dict:
    """Produce a `Glass3DData` dict (same shape as `/games/{id}/glass-3d`).

    No game session required. Mirrors the session endpoint's pipeline.
    """
    holes = _render_holes_for(course)
    if not holes:
        raise ValueError("course has no holes")

    groups = split_into_glasses(holes, glass_count)
    idx = max(0, min(glass_number - 1, len(groups) - 1))
    glass_holes = groups[idx]

    layout = compute_layout(glass_holes, {"canvas_width": 900, "canvas_height": 700})
    zones_by_hole = compute_all_scoring_zones(layout)
    add_scoring_features_to_layout(layout, zones_by_hole)

    draw_area = layout.get("draw_area", {})
    canvas_top = draw_area.get("top", 0)
    canvas_bottom = draw_area.get("bottom", layout.get("canvas_height", 700))
    canvas_range = canvas_bottom - canvas_top if canvas_bottom != canvas_top else 1

    template = compute_glass_template()
    terrain_zones = compute_all_terrain_following_zones(layout)
    warped = warp_layout(layout, template)

    tz_dicts: list[Any] | None = None
    if terrain_zones is not None:
        tz_dicts = [
            [
                {
                    "score": tz.score,
                    "polygon": tz.polygon,
                    "y_center": tz.y_center,
                    "y_top": tz.y_top,
                    "y_bottom": tz.y_bottom,
                    "label_position": tz.label_position,
                    "leader_line": tz.leader_line,
                }
                for tz in hole_tzs
            ]
            for hole_tzs in terrain_zones
        ]

    svg_opts = {
        "styles": {},
        "hidden_layers": ["background"],
        "per_hole_colors": True,
        "course_name": course.get("name") or course.get("club_name") or "",
        "zones_by_hole": zones_by_hole,
        "vinyl_preview": True,
        "show_glass_outline": False,
    }
    if tz_dicts:
        svg_opts["terrain_zones"] = tz_dicts

    wrap_svg = render_svg(warped, svg_opts)

    zones_with_fracs = []
    for hole_zones in zones_by_hole:
        zones_out = []
        for zone in hole_zones.get("zones", []):
            frac_top = (zone["y_top"] - canvas_top) / canvas_range
            frac_bottom = (zone["y_bottom"] - canvas_top) / canvas_range
            zones_out.append({
                "score": zone["score"],
                "y_top": zone["y_top"],
                "y_bottom": zone["y_bottom"],
                "label": zone["label"],
                "position": zone.get("position", "above"),
                "height_frac_top": round(frac_top, 4),
                "height_frac_bottom": round(frac_bottom, 4),
            })
        zones_with_fracs.append({
            "hole_ref": hole_zones.get("hole_ref", 0),
            "zones": zones_out,
        })

    return {
        "wrap_svg": wrap_svg,
        "zones_by_hole": zones_with_fracs,
        "glass_template": {
            "glass_height": template["glass_height"],
            "top_radius": template["top_radius"],
            "bottom_radius": template["bottom_radius"],
            "wall_thickness": template["wall_thickness"],
            "base_thickness": template["base_thickness"],
            "inner_r": template["inner_r"],
            "outer_r": template["outer_r"],
            "sector_angle": template["sector_angle"],
            "sector_angle_deg": template["sector_angle_deg"],
            "slant_height": template["slant_height"],
            "volume_ml": template["volume_ml"],
        },
        "holes_per_glass": len(glass_holes),
    }


def _render_holes_for(course: dict) -> list[dict]:
    """Holes list normalized for layout/render: {number, par, yards, handicap}."""
    raw = course.get("render_holes") or course.get("holes") or []
    if raw and raw[0].get("yards") is not None:
        return raw
    normalized = []
    for h in raw:
        normalized.append({
            "number": h.get("number"),
            "par": h.get("par", 4),
            "yards": h.get("yardage") or h.get("yards") or 0,
            "handicap": h.get("handicap") or 0,
        })
    return normalized


def course_hash(course: dict) -> str:
    """Stable hash of the course fields that affect product output."""
    parts = [
        str(course.get("id") or course.get("course_id") or ""),
        (course.get("name") or ""),
        (course.get("club_name") or ""),
    ]
    loc = course.get("location") or {}
    parts.extend([loc.get("city") or "", loc.get("state") or "", loc.get("country") or ""])
    for t in course.get("tees") or []:
        parts.append(f"tee:{t.get('tee_name')}")
        for h in t.get("holes") or []:
            parts.append(f"{h.get('number')}|{h.get('par')}|{h.get('yardage')}|{h.get('handicap')}")
    for h in course.get("holes") or []:
        parts.append(f"h:{h.get('number')}|{h.get('par')}|{h.get('yardage')}|{h.get('handicap')}")
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
