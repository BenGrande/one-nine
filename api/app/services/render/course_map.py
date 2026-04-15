"""Render overhead course map SVG from raw OSM features (lat/lng polygons)."""
from __future__ import annotations

import math

# Colors matching real aerial/satellite map aesthetics
CATEGORY_STYLES = {
    "course_boundary": {"fill": "#3d6b3d", "stroke": "none", "opacity": 0.15},
    "rough":           {"fill": "#6b8e5a", "stroke": "none", "opacity": 0.5},
    "fairway":         {"fill": "#5aad47", "stroke": "#4a9a3a", "opacity": 0.85},
    "green":           {"fill": "#4ecc3e", "stroke": "#3aaa2e", "opacity": 0.95},
    "tee":             {"fill": "#6bc95c", "stroke": "#52a846", "opacity": 0.9},
    "bunker":          {"fill": "#e8dca0", "stroke": "#cfc27a", "opacity": 0.9},
    "water":           {"fill": "#5b9bd5", "stroke": "#4a87be", "opacity": 0.85},
    "path":            {"fill": "none", "stroke": "#b8a88a", "opacity": 0.5},
}

# Render order (back to front)
LAYER_ORDER = ["course_boundary", "rough", "water", "fairway", "bunker", "tee", "green", "path"]


def _project(lat: float, lng: float, center_lat: float, center_lng: float) -> tuple[float, float]:
    """Simple equirectangular projection from lat/lng to x/y meters."""
    cos_lat = math.cos(math.radians(center_lat))
    x = (lng - center_lng) * cos_lat * 111320
    y = -(lat - center_lat) * 110540  # negative because SVG y goes down
    return x, y


def render_course_map_svg(
    features: list[dict],
    center: list[float],
    width: int = 600,
    height: int = 300,
) -> str:
    """Render overhead course map SVG from OSM features.

    Args:
        features: List of feature dicts with 'category', 'coords' (lat/lng pairs), etc.
        center: [lat, lng] center point of the course.
        width: SVG width in pixels.
        height: SVG height in pixels.

    Returns:
        SVG string of the course map.
    """
    if not features:
        return ""

    center_lat, center_lng = center[0], center[1]

    # Project all coordinates
    projected: list[tuple[str, list[tuple[float, float]], dict]] = []
    all_x, all_y = [], []

    for f in features:
        cat = f.get("category", "")
        coords = f.get("coords", [])
        if not coords or cat not in CATEGORY_STYLES:
            continue

        pts = []
        for c in coords:
            x, y = _project(c[0], c[1], center_lat, center_lng)
            pts.append((x, y))
            all_x.append(x)
            all_y.append(y)

        projected.append((cat, pts, f))

    if not all_x:
        return ""

    # Compute bounding box with padding
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    data_w = max_x - min_x or 1
    data_h = max_y - min_y or 1

    pad_frac = 0.05
    pad_x = data_w * pad_frac
    pad_y = data_h * pad_frac
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y
    data_w = max_x - min_x
    data_h = max_y - min_y

    # Scale to fit SVG while preserving aspect ratio
    scale = min(width / data_w, height / data_h)
    svg_w = data_w * scale
    svg_h = data_h * scale
    offset_x = (width - svg_w) / 2
    offset_y = (height - svg_h) / 2

    def to_svg(x: float, y: float) -> tuple[float, float]:
        return (x - min_x) * scale + offset_x, (y - min_y) * scale + offset_y

    # Sort features by layer order
    order_map = {cat: i for i, cat in enumerate(LAYER_ORDER)}
    projected.sort(key=lambda p: order_map.get(p[0], 99))

    # Build SVG
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'style="max-width:100%;height:auto;">'
    )

    # Background
    svg += f'<rect width="{width}" height="{height}" fill="#1a3a1a" rx="8"/>'

    # Render features
    for cat, pts, feat in projected:
        style = CATEGORY_STYLES[cat]
        svg_pts = [to_svg(x, y) for x, y in pts]

        if cat == "path":
            # Render as polyline
            points_str = " ".join(f"{_ff(x)},{_ff(y)}" for x, y in svg_pts)
            svg += (
                f'<polyline points="{points_str}" '
                f'fill="none" stroke="{style["stroke"]}" '
                f'stroke-width="1" opacity="{style["opacity"]}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        elif len(svg_pts) >= 3:
            # Render as polygon
            points_str = " ".join(f"{_ff(x)},{_ff(y)}" for x, y in svg_pts)
            stroke_attr = f'stroke="{style["stroke"]}" stroke-width="0.5"' if style["stroke"] != "none" else 'stroke="none"'
            svg += (
                f'<polygon points="{points_str}" '
                f'fill="{style["fill"]}" {stroke_attr} '
                f'opacity="{style["opacity"]}"/>'
            )

    # Render hole labels (green centroids with hole number)
    for cat, pts, feat in projected:
        if cat != "green" or not feat.get("ref"):
            continue
        svg_pts = [to_svg(x, y) for x, y in pts]
        cx = sum(p[0] for p in svg_pts) / len(svg_pts)
        cy = sum(p[1] for p in svg_pts) / len(svg_pts)
        # Small circle + number
        svg += (
            f'<circle cx="{_ff(cx)}" cy="{_ff(cy)}" r="6" '
            f'fill="rgba(0,0,0,0.6)" stroke="white" stroke-width="0.5"/>'
        )
        svg += (
            f'<text x="{_ff(cx)}" y="{_ff(cy + 1.5)}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="5" font-family="Arial,sans-serif" '
            f'fill="white" font-weight="bold">{feat["ref"]}</text>'
        )

    # Also label holes from "hole" category features (lines from tee to green)
    for cat, pts, feat in projected:
        if cat != "hole" or not feat.get("ref"):
            continue
        # Use the green-end (last point) of the hole line for label
        if len(pts) >= 2:
            svg_pts = [to_svg(x, y) for x, y in pts]
            # Draw a thin line for the hole routing
            points_str = " ".join(f"{_ff(x)},{_ff(y)}" for x, y in svg_pts)
            svg += (
                f'<polyline points="{points_str}" '
                f'fill="none" stroke="rgba(255,255,255,0.15)" '
                f'stroke-width="1" stroke-dasharray="3,2"/>'
            )

    svg += "</svg>"
    return svg


def _ff(v: float) -> str:
    """Format float for SVG."""
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}"
