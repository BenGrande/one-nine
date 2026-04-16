"""Glass template — unwrapped vinyl wrap shape for tapered pint glass."""
from __future__ import annotations

import math


def compute_glass_template(opts: dict | None = None) -> dict:
    """Compute the unwrapped glass template geometry."""
    opts = opts or {}
    glass_height = opts.get("glass_height", 150)
    top_radius = opts.get("top_radius", 44)
    bottom_radius = opts.get("bottom_radius", 30)
    wall_thickness = opts.get("wall_thickness", 3.1)
    base_thickness = opts.get("base_thickness", 16.5)

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

    inner_top_r = template["top_radius"] - template.get("wall_thickness", 3.1)
    inner_bot_r = template["bottom_radius"] - template.get("wall_thickness", 3.1)
    inner_h = glass_height - template.get("base_thickness", 16.5)
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
    outer_fill_h = template.get("base_thickness", 16.5) + fill_h
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

    # Find bounding box of visible content INCLUDING stats box positions.
    # Stats boxes sit beside the hole number circle on the outer side.
    min_x = min_y = math.inf
    max_x = max_y = -math.inf

    stats_box_w = 13  # must match svg.py _render_hole_stats box_w for warped
    cr = 2.5  # hole number circle radius in warped mode (must match svg.py)

    for hole in layout["holes"]:
        # Basic hole bounds
        min_x = min(min_x, hole["start_x"] - 16)
        max_x = max(max_x, hole["start_x"] + 16)
        min_y = min(min_y, hole["start_y"] - 6)
        max_y = max(max_y, hole["start_y"] + 20)

        # Feature bounds (skip synthetic scoring features to avoid expanding bounds)
        for f in hole["features"]:
            if f.get("category") in ("zone_line", "zone_label", "zone_label_external"):
                continue
            for x, y in f["coords"]:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

        # Stats box bounds — box is BELOW tee, offset to tee side
        tee_x = hole["start_x"]
        tee_y = hole["start_y"]
        direction = hole.get("direction", 1)
        if direction > 0:
            box_cx = tee_x - stats_box_w / 2 - 2
        else:
            box_cx = tee_x + stats_box_w / 2 + 2
        box_x = box_cx - stats_box_w / 2
        box_h_est = 14  # circle + 3 lines of text
        box_y = tee_y + 2
        min_x = min(min_x, box_x - 1)
        max_x = max(max_x, box_x + stats_box_w + 1)
        max_y = max(max_y, box_y + box_h_est + 1)

    # Small general padding
    min_x -= 8
    max_x += 8
    min_y -= 10
    max_y += 10
    content_w = max_x - min_x
    content_h = max_y - min_y

    # Two-column layouts need more left-side angular space to fit BOTH the
    # course title text AND the left score ruler without the columns
    # overflowing into that area.
    is_two_column = layout.get("layout_mode") == "two_column"
    text_reserve = 0.22 if is_two_column else 0.14
    right_reserve = 0.17
    inner_r = template["inner_r"]
    outer_r = template["outer_r"]
    sector_angle = template["sector_angle"]
    half_angle = sector_angle / 2

    edge_inset = 0.05
    radial_span = outer_r - inner_r  # = slant height
    # Reserve the base thickness + 7mm extra at the bottom so content
    # stays above the solid glass base with room for leftover beer.
    base_mm = template.get("base_thickness", 16.5)
    base_reserve = (base_mm + 7) / radial_span if radial_span > 0 else 0
    r_top = outer_r - radial_span * (edge_inset + top_pad)
    r_bot = inner_r + radial_span * (max(edge_inset, base_reserve) + bot_pad)

    def warp_pt(x, y):
        nx = text_reserve + ((x - min_x) / content_w) * (1 - text_reserve - right_reserve)
        ny = (y - min_y) / content_h
        r = r_top - ny * (r_top - r_bot)
        angle = -half_angle + nx * sector_angle
        return [r * math.sin(angle), -r * math.cos(angle)]

    warped_holes = []
    for hole in layout["holes"]:
        sx, sy = warp_pt(hole["start_x"], hole["start_y"])
        ex, ey = warp_pt(hole["end_x"], hole["end_y"])
        warped_hole = {
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
        }
        # Warp the info-box target position (two-column layout) using the
        # hole's rect-space tee Y so the box sits on the same radial line.
        if "_info_box_cx" in hole and "_info_box_cy" in hole:
            ibx, iby = warp_pt(hole["_info_box_cx"], hole["_info_box_cy"])
            warped_hole["_info_box_cx"] = ibx
            warped_hole["_info_box_cy"] = iby
        warped_holes.append(warped_hole)

    from app.services.render.layout import _enforce_slope, _resolve_info_box_overlaps
    _enforce_slope(warped_holes)

    # Re-resolve info-box overlaps in warped coordinates. The sector warp
    # compresses vertical gaps near the glass edge, so boxes that looked
    # clear in rect space can visually overlap features after warping.
    if layout.get("layout_mode") == "two_column":
        # Per-Y minimum X: the left ruler's right edge (local x=18) in the
        # rotated frame maps to a world line whose X varies with Y. Solve
        # for y_local then take x_world = 18*cos(rot) - y_local*sin(rot).
        ruler_edge = -half_angle + 0.07
        r_cos = math.cos(ruler_edge)
        r_sin = math.sin(ruler_edge)
        local_right_x = 18
        box_half_w = 6.5
        clearance = 3

        def _min_cx_for_y(y_world: float) -> float:
            y_local = (y_world - local_right_x * r_sin) / r_cos
            y_local = max(-r_top, min(-r_bot, y_local))
            x_world = local_right_x * r_cos - y_local * r_sin
            return x_world + box_half_w + clearance

        _resolve_info_box_overlaps(
            warped_holes, box_w=13, box_h=17,
            safety=1, max_shift=60, step=1.5,
            min_cx_fn=_min_cx_for_y,
        )

    return {
        **layout,
        "holes": warped_holes,
        "warped": True,
        "template": template,
        # Warp parameters so ruler can use the same y→r conversion
        "_warp_min_y": min_y,
        "_warp_content_h": content_h,
        "_warp_r_top": r_top,
        "_warp_r_bot": r_bot,
    }
