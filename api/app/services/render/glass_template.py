"""Glass template — unwrapped vinyl wrap shape for tapered pint glass."""
from __future__ import annotations

import math


def compute_glass_template(opts: dict | None = None) -> dict:
    """Compute the unwrapped glass template geometry."""
    opts = opts or {}
    glass_height = opts.get("glass_height", 146)
    top_radius = opts.get("top_radius", 43)
    bottom_radius = opts.get("bottom_radius", 30)
    wall_thickness = opts.get("wall_thickness", 3)
    base_thickness = opts.get("base_thickness", 5)

    top_circumference = 2 * math.pi * top_radius
    bottom_circumference = 2 * math.pi * bottom_radius

    radius_diff = top_radius - bottom_radius
    slant_height = math.sqrt(glass_height ** 2 + radius_diff ** 2)

    # Apex distance from bottom
    d = (bottom_radius * slant_height) / radius_diff if radius_diff != 0 else math.inf

    inner_r = d
    outer_r = d + slant_height

    # Sector angle
    sector_angle = bottom_circumference / inner_r if inner_r > 0 else 0

    # SVG dimensions
    svg_width = outer_r * 2 * math.sin(sector_angle / 2) + 20
    svg_height = outer_r - inner_r * math.cos(sector_angle / 2) + 20

    # Inner volume (truncated cone)
    inner_top_r = top_radius - wall_thickness
    inner_bot_r = bottom_radius - wall_thickness
    inner_height = glass_height - base_thickness
    volume_mm3 = (math.pi * inner_height / 3) * (
        inner_top_r ** 2 + inner_bot_r ** 2 + inner_top_r * inner_bot_r
    )
    volume_ml = volume_mm3 / 1000

    return {
        "glass_height": glass_height,
        "top_radius": top_radius,
        "bottom_radius": bottom_radius,
        "top_circumference": top_circumference,
        "bottom_circumference": bottom_circumference,
        "slant_height": slant_height,
        "inner_r": inner_r,
        "outer_r": outer_r,
        "sector_angle": sector_angle,
        "sector_angle_deg": sector_angle * 180 / math.pi,
        "svg_width": svg_width,
        "svg_height": svg_height,
        "d": d,
        "volume_ml": volume_ml,
        "wall_thickness": wall_thickness,
        "base_thickness": base_thickness,
    }


def compute_fill_height(template: dict, volume_ml: float) -> dict:
    """Compute fill height (from bottom) for a given liquid volume."""
    total_vol = template["volume_ml"]
    glass_height = template["glass_height"]
    if volume_ml >= total_vol:
        return {"height_mm": glass_height, "fraction": 1.0}

    inner_top_r = template["top_radius"] - template.get("wall_thickness", 3)
    inner_bot_r = template["bottom_radius"] - template.get("wall_thickness", 3)
    inner_h = glass_height - template.get("base_thickness", 5)
    target_mm3 = volume_ml * 1000

    lo, hi = 0.0, inner_h
    for _ in range(50):
        mid = (lo + hi) / 2
        r_mid = inner_bot_r + (inner_top_r - inner_bot_r) * mid / inner_h
        vol = (math.pi * mid / 3) * (inner_bot_r ** 2 + r_mid ** 2 + inner_bot_r * r_mid)
        if vol < target_mm3:
            lo = mid
        else:
            hi = mid

    fill_h = (lo + hi) / 2
    outer_fill_h = template.get("base_thickness", 5) + fill_h
    return {"height_mm": outer_fill_h, "fraction": outer_fill_h / glass_height}


def glass_wrap_path(template: dict) -> str:
    """Generate SVG path for the glass wrap outline."""
    inner_r = template["inner_r"]
    outer_r = template["outer_r"]
    sector_angle = template["sector_angle"]
    half_angle = sector_angle / 2

    blx = -inner_r * math.sin(half_angle)
    bly = -inner_r * math.cos(half_angle)
    brx = inner_r * math.sin(half_angle)
    bry = -inner_r * math.cos(half_angle)
    tlx = -outer_r * math.sin(half_angle)
    tly = -outer_r * math.cos(half_angle)
    trx = outer_r * math.sin(half_angle)
    try_ = -outer_r * math.cos(half_angle)

    large_arc = 1 if sector_angle > math.pi else 0

    return " ".join([
        f"M {tlx:.2f} {tly:.2f}",
        f"A {outer_r:.2f} {outer_r:.2f} 0 {large_arc} 1 {trx:.2f} {try_:.2f}",
        f"L {brx:.2f} {bry:.2f}",
        f"A {inner_r:.2f} {inner_r:.2f} 0 {large_arc} 0 {blx:.2f} {bly:.2f}",
        "Z",
    ])


def create_warp_function(template: dict, rect_width: float, rect_height: float):
    """Create a warp function mapping rect coords to glass polar coords."""
    inner_r = template["inner_r"]
    outer_r = template["outer_r"]
    sector_angle = template["sector_angle"]
    half_angle = sector_angle / 2

    def warp(x: float, y: float) -> list[float]:
        nx = x / rect_width
        ny = y / rect_height
        r = outer_r - ny * (outer_r - inner_r)
        angle = -half_angle + nx * sector_angle
        wx = r * math.sin(angle)
        wy = -r * math.cos(angle)
        return [wx, wy]

    return warp


def warp_layout(layout: dict, template: dict, padding_opts: dict | None = None) -> dict:
    """Warp an entire layout to glass space."""
    top_pad = (padding_opts or {}).get("top_padding", 0)
    bot_pad = (padding_opts or {}).get("bottom_padding", 0)

    # Find bounding box of visible content
    min_x = min_y = math.inf
    max_x = max_y = -math.inf

    for hole in layout["holes"]:
        min_x = min(min_x, hole["start_x"] - 16)
        max_x = max(max_x, hole["start_x"] + 16)
        min_y = min(min_y, hole["start_y"] - 6)
        max_y = max(max_y, hole["start_y"] + 20)
        for f in hole["features"]:
            for x, y in f["coords"]:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

    pad = 20
    min_x -= pad
    min_y -= pad
    max_x += pad
    max_y += pad
    content_w = max_x - min_x
    content_h = max_y - min_y

    text_reserve = 0.10
    inner_r = template["inner_r"]
    outer_r = template["outer_r"]
    sector_angle = template["sector_angle"]
    half_angle = sector_angle / 2

    edge_inset = 0.05
    r_top = outer_r - (outer_r - inner_r) * (edge_inset + top_pad)
    r_bot = inner_r + (outer_r - inner_r) * (edge_inset + bot_pad)

    def warp_pt(x, y):
        nx = text_reserve + ((x - min_x) / content_w) * (1 - text_reserve - 0.20)
        ny = (y - min_y) / content_h
        r = r_top - ny * (r_top - r_bot)
        angle = -half_angle + nx * sector_angle
        return [r * math.sin(angle), -r * math.cos(angle)]

    warped_holes = []
    for hole in layout["holes"]:
        sx, sy = warp_pt(hole["start_x"], hole["start_y"])
        ex, ey = warp_pt(hole["end_x"], hole["end_y"])
        warped_holes.append({
            **hole,
            "start_x": sx,
            "start_y": sy,
            "end_x": ex,
            "end_y": ey,
            "features": [
                {
                    **f,
                    "coords": [warp_pt(x, y) for x, y in f["coords"]],
                }
                for f in hole["features"]
            ],
        })

    from app.services.render.layout import _enforce_slope
    _enforce_slope(warped_holes)

    return {
        **layout,
        "holes": warped_holes,
        "warped": True,
        "template": template,
    }
