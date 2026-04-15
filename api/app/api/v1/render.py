"""Render endpoints — layout computation and SVG generation."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.services.game import generate_qr_svg, get_or_create_glass_set
from app.services.render.layout import compute_layout, split_into_glasses
from app.services.render.svg import render_svg
from app.services.render.scoring import compute_all_scoring_zones, compute_all_terrain_following_zones
from app.services.render.cricut import (
    render_cricut_white,
    render_cricut_green,
    render_cricut_tan,
    render_cricut_blue,
    render_cricut_guide,
)
from app.services.render.glass_template import (
    compute_glass_template,
    glass_wrap_path,
    warp_layout,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_hole_stats(holes: list[dict]) -> dict[int, dict]:
    """Extract per-hole stats (par, yards, handicap) from hole data."""
    stats: dict[int, dict] = {}
    for h in holes:
        ref = h.get("ref") or h.get("number")
        if ref is None:
            continue
        ref = int(ref)
        stats[ref] = {
            "par": h.get("par", 4),
            "yards": h.get("yards") or h.get("yardage", 0),
            "handicap": h.get("handicap", 0),
        }
    return stats


async def _render_course_map_svg(
    holes: list[dict],
    course_name: str = "",
    course_lat: float | None = None,
    course_lng: float | None = None,
) -> str:
    """Render overhead course map SVG from real OSM features."""
    from app.services.render.course_map import render_course_map_svg

    hole_stats = _build_hole_stats(holes)

    # If we have lat/lng, fetch the real OSM features for the overhead map
    if course_lat and course_lng:
        try:
            from app.services.golf.osm import fetch_course_map
            map_data = await fetch_course_map(course_lat, course_lng)
            features = map_data.get("features", [])
            center = map_data.get("center", [course_lat, course_lng])
            if features:
                return render_course_map_svg(
                    features, center, width=600, height=300, hole_stats=hole_stats,
                )
        except Exception as exc:
            logger.warning("Real course map fetch failed: %s", exc)

    # Fallback: build map from hole features themselves (they have coords)
    all_features = []
    for h in holes:
        for f in h.get("features", []):
            all_features.append(f)

    if all_features:
        all_lats, all_lngs = [], []
        for f in all_features:
            for c in f.get("coords", []):
                all_lats.append(c[0])
                all_lngs.append(c[1])
        if all_lats:
            center = [sum(all_lats) / len(all_lats), sum(all_lngs) / len(all_lngs)]
            return render_course_map_svg(
                all_features, center, width=600, height=300, hole_stats=hole_stats,
            )

    # Final fallback: glass-layout-style render
    try:
        layout = compute_layout(holes, {"canvas_width": 600, "canvas_height": 400})
        svg_opts = {
            "styles": {},
            "hidden_layers": ["ruler", "hole_par", "hole_stats"],
            "per_hole_colors": True,
            "course_name": course_name,
        }
        return render_svg(layout, svg_opts)
    except Exception as exc:
        logger.warning("Course map SVG generation failed: %s", exc)
        return ""


def _build_layout_and_zones(holes, options):
    """Shared helper: compute layout, zones, and optionally warp."""
    mode = options.get("mode", "rect")
    layout_opts = {
        "canvas_width": options.get("canvas_width", 900),
        "canvas_height": options.get("canvas_height", 700),
    }
    layout = compute_layout(holes, layout_opts)
    zone_ratios = options.get("zone_ratios")
    zones_by_hole = compute_all_scoring_zones(layout, zone_ratios)

    # Inject scoring visual elements as synthetic features BEFORE warping
    from app.services.render.scoring import add_scoring_features_to_layout
    add_scoring_features_to_layout(layout, zones_by_hole)

    terrain_zones = None
    if mode in ("glass", "vinyl-preview", "scoring-preview", "cricut-white", "cricut-all"):
        terrain_zones = compute_all_terrain_following_zones(layout, zone_ratios)

    template = None
    if mode in ("glass", "vinyl-preview", "cricut-white", "cricut-green", "cricut-tan", "cricut-blue", "cricut-all"):
        template = compute_glass_template(options.get("glass_dimensions") or options.get("glass_template"))
        layout = warp_layout(layout, template, options.get("padding"))

    return layout, zones_by_hole, terrain_zones, template


@router.post("/render")
async def render(data: dict):
    """Compute layout and render SVG from hole data."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")
    holes = data.get("holes")
    if holes is None:
        raise HTTPException(status_code=422, detail="Missing required field: holes")
    if not isinstance(holes, list):
        raise HTTPException(status_code=422, detail="holes must be an array")
    options = data.get("options", {})

    # Allow course_name at top level or inside options
    if "course_name" in data and "course_name" not in options:
        options["course_name"] = data["course_name"]

    # Allow hole_range at top level or inside options
    if "hole_range" in data and "hole_range" not in options:
        options["hole_range"] = data["hole_range"]

    # Auto-compute hole_range if not provided
    if "hole_range" not in options and holes:
        refs = [h.get("ref") for h in holes if h.get("ref") is not None]
        if refs:
            options["hole_range"] = f"Holes {min(refs)}-{max(refs)}"

    glass_count = options.get("glass_count", 1)
    current_glass = options.get("current_glass", 0)
    mode = options.get("mode", "rect")

    # Auto-create glass set for QR codes
    glass_set_id = options.get("glass_set_id")
    glass_set = None
    if mode in ("glass", "vinyl-preview"):
        try:
            course_name = options.get("course_name", "Course")
            holes_per_glass = len(holes) // glass_count if glass_count else len(holes)
            # Generate real overhead course map SVG for the scorecard
            course_map_svg = await _render_course_map_svg(
                holes, course_name,
                course_lat=options.get("course_lat"),
                course_lng=options.get("course_lng"),
            )
            glass_set = await get_or_create_glass_set(
                glass_set_id=glass_set_id,
                course_name=course_name,
                glass_count=glass_count,
                holes_per_glass=holes_per_glass,
                recipient_name=options.get("recipient_name", ""),
                course_id=options.get("course_id", ""),
                holes=holes,
                course_lat=options.get("course_lat"),
                course_lng=options.get("course_lng"),
                course_map_svg=course_map_svg,
            )
            glass_set_id = glass_set.get("_id") or glass_set.get("id")
        except Exception as exc:
            logger.warning("Glass set creation failed: %s", exc)

    # Split holes into glasses
    groups = split_into_glasses(holes, glass_count)

    holes_per_glass = options.get("holes_per_glass")
    if holes_per_glass and len(holes) > holes_per_glass:
        groups = split_into_glasses(holes, max(1, len(holes) // holes_per_glass))

    # If current_glass specified, only render that one
    if current_glass is not None and 0 <= current_glass < len(groups):
        groups = [groups[current_glass]]

    results = []
    for group in groups:
        layout, zones_by_hole, terrain_zones, template = _build_layout_and_zones(group, options)

        # Serialize terrain zones for cricut
        tz_dicts = None
        if terrain_zones is not None:
            tz_dicts = [
                [{"score": tz.score, "polygon": tz.polygon,
                  "y_center": tz.y_center, "y_top": tz.y_top, "y_bottom": tz.y_bottom,
                  "label_position": tz.label_position,
                  "leader_line": tz.leader_line}
                 for tz in hole_tzs]
                for hole_tzs in terrain_zones
            ]

        # Handle Cricut modes
        if mode == "cricut-white":
            svg = render_cricut_white(layout, zones_by_hole, template, options, terrain_zones=tz_dicts)
            results.append({"svg": svg, "layout": layout, "zones": zones_by_hole})
            continue
        if mode == "cricut-green":
            svg = render_cricut_green(layout, options)
            results.append({"svg": svg, "layout": layout, "zones": zones_by_hole})
            continue
        if mode == "cricut-tan":
            svg = render_cricut_tan(layout, options)
            results.append({"svg": svg, "layout": layout, "zones": zones_by_hole})
            continue
        if mode == "cricut-blue":
            svg = render_cricut_blue(layout, options)
            results.append({"svg": svg, "layout": layout, "zones": zones_by_hole})
            continue
        if mode == "cricut-all":
            results.append({
                "white": render_cricut_white(layout, zones_by_hole, template, options, terrain_zones=tz_dicts),
                "green": render_cricut_green(layout, options),
                "tan": render_cricut_tan(layout, options),
                "blue": render_cricut_blue(layout, options),
                "guide": render_cricut_guide(layout, options),
                "layout": layout,
                "zones": zones_by_hole,
            })
            continue

        # Standard render modes
        svg_opts = {
            "styles": options.get("styles", {}),
            "hidden_layers": options.get("hidden_layers", []),
            "font_family": options.get("font_family"),
            "course_name": options.get("course_name"),
            "hole_range": options.get("hole_range"),
            "logo_data_url": options.get("logo_data_url"),
            "hole_yardages": options.get("hole_yardages"),
            "per_hole_colors": options.get("per_hole_colors", True),
            "show_glass_outline": options.get("show_glass_outline", True),
            "zones_by_hole": zones_by_hole,
            "scoring_preview": mode in ("scoring-preview", "vinyl-preview"),
            "qr_svg": options.get("qr_svg") or (
                glass_set["qr_codes"][current_glass or 0]["qr_svg"]
                if glass_set and glass_set.get("qr_codes")
                and len(glass_set["qr_codes"]) > (current_glass or 0)
                else generate_qr_svg(
                    f"http://agentcll.local:6969/play/{glass_set_id}"
                    if glass_set_id
                    else "http://agentcll.local:6969"
                )
            ),
            "show_score_lines": options.get("show_score_lines", False),
        }
        if mode in ("glass", "vinyl-preview", "scoring-preview"):
            if mode in ("glass", "vinyl-preview"):
                svg_opts["vinyl_preview"] = True
            if terrain_zones is not None:
                svg_opts["terrain_zones"] = [
                    [{"score": tz.score, "polygon": tz.polygon,
                      "y_center": tz.y_center, "y_top": tz.y_top, "y_bottom": tz.y_bottom,
                      "label_position": tz.label_position,
                      "leader_line": tz.leader_line}
                     for tz in hole_tzs]
                    for hole_tzs in terrain_zones
                ]
        svg = render_svg(layout, svg_opts)

        result_entry = {
            "svg": svg,
            "layout": layout,
            "zones": zones_by_hole,
            "glass_set_id": glass_set_id,
        }
        if terrain_zones is not None:
            result_entry["terrain_zones"] = [
                [{"score": tz.score, "polygon": tz.polygon,
                  "y_center": tz.y_center, "y_top": tz.y_top, "y_bottom": tz.y_bottom,
                  "label_position": tz.label_position,
                  "leader_line": tz.leader_line}
                 for tz in hole_tzs]
                for hole_tzs in terrain_zones
            ]
        results.append(result_entry)

    if len(results) == 1:
        return results[0]
    return {"glasses": results}


@router.post("/render/cricut")
async def render_cricut(data: dict):
    """Render all three Cricut vinyl layers + placement guide."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")
    holes = data.get("holes")
    if holes is None:
        raise HTTPException(status_code=422, detail="Missing required field: holes")
    if not isinstance(holes, list):
        raise HTTPException(status_code=422, detail="holes must be an array")
    if not holes:
        raise HTTPException(status_code=400, detail="holes array must not be empty")
    options = data.get("options", {})

    # Allow course_name at top level or inside options
    if "course_name" in data and "course_name" not in options:
        options["course_name"] = data["course_name"]

    # Allow hole_range at top level or inside options
    if "hole_range" in data and "hole_range" not in options:
        options["hole_range"] = data["hole_range"]

    # Compute hole_range if not provided
    if "hole_range" not in options and holes:
        refs = [h.get("ref") for h in holes if h.get("ref") is not None]
        if refs:
            options["hole_range"] = f"Holes {min(refs)}-{max(refs)}"

    glass_count = options.get("glass_count", 1)
    groups = split_into_glasses(holes, glass_count)

    results = []
    for gi, group in enumerate(groups):
        try:
            layout_opts = {
                "canvas_width": options.get("canvas_width", 900),
                "canvas_height": options.get("canvas_height", 700),
            }
            layout = compute_layout(group, layout_opts)
            zone_ratios = options.get("zone_ratios")
            zones_by_hole = compute_all_scoring_zones(layout, zone_ratios)

            # Inject scoring features before warping
            from app.services.render.scoring import add_scoring_features_to_layout
            add_scoring_features_to_layout(layout, zones_by_hole)

            # Compute terrain zones before warping (they use flat layout coordinates)
            tf_zones = compute_all_terrain_following_zones(layout, zone_ratios)
            tz_cricut = [
                [{"score": tz.score, "polygon": tz.polygon,
                  "y_center": tz.y_center, "y_top": tz.y_top, "y_bottom": tz.y_bottom,
                  "label_position": tz.label_position,
                  "leader_line": tz.leader_line}
                 for tz in hole_tzs]
                for hole_tzs in tf_zones
            ] if tf_zones else None

            template = compute_glass_template(options.get("glass_dimensions") or options.get("glass_template"))
            warped_layout = warp_layout(layout, template, options.get("padding"))

            layers = {
                "white": render_cricut_white(warped_layout, zones_by_hole, template, options, terrain_zones=tz_cricut),
                "green": render_cricut_green(warped_layout, options),
                "tan": render_cricut_tan(warped_layout, options),
                "blue": render_cricut_blue(warped_layout, options),
                "guide": render_cricut_guide(warped_layout, options),
            }

            # Validate all layers are non-empty SVG strings
            for layer_name, svg_str in layers.items():
                if not svg_str or not isinstance(svg_str, str) or "<svg" not in svg_str:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Cricut layer '{layer_name}' produced empty or invalid SVG (glass {gi})",
                    )

            results.append(layers)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to render cricut layers for glass {gi}: {exc}",
            )

    if len(results) == 1:
        return results[0]
    return {"glasses": results}


@router.post("/render/glass-template")
async def get_glass_template(data: dict | None = None):
    """Compute glass template geometry."""
    template = compute_glass_template(data)
    path = glass_wrap_path(template)
    return {"template": template, "path": path}
