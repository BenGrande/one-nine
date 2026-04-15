"""SVG renderer — produces SVG from layout data."""
from __future__ import annotations

import math
import re

DEFAULT_STYLES = {
    "course_boundary": {"fill": "#3d6b3d", "stroke": "#2d5a2d", "stroke_width": 0.5, "opacity": 0.2},
    "rough": {"fill": "#8ab878", "stroke": "none", "stroke_width": 0, "opacity": 0.5},
    "fairway": {"fill": "#4a8f3f", "stroke": "#3d7a34", "stroke_width": 0.3, "opacity": 0.85},
    "bunker": {"fill": "#e8dca0", "stroke": "#d4c87a", "stroke_width": 0.3, "opacity": 0.9},
    "water": {"fill": "#5b9bd5", "stroke": "#4a87be", "stroke_width": 0.3, "opacity": 0.85},
    "tee": {"fill": "#7bc96a", "stroke": "#5eaa50", "stroke_width": 0.3, "opacity": 0.9},
    "green": {"fill": "#5cc654", "stroke": "#3eaa36", "stroke_width": 0.5, "opacity": 0.95},
    "hole_number": {"fill": "rgba(0,0,0,0.65)", "stroke": "#ffffff", "stroke_width": 0.4, "opacity": 1},
    "hole_par": {"fill": "rgba(255,255,255,0.5)", "stroke": "none", "stroke_width": 0, "opacity": 1},
    "background": {"fill": "#1a472a"},
}

ALL_LAYERS = [
    "background", "rough", "fairway", "water", "bunker", "tee", "green",
    "hole_number", "hole_par", "hole_stats", "ruler",
]

FEATURE_LAYERS = ["rough", "water", "fairway", "bunker", "tee", "green"]

HOLE_HUES = [120, 150, 90, 180, 60, 200, 100, 160, 75, 130, 170, 80, 190, 55, 210, 110, 145, 85]

# Scoring preview zone colors
ZONE_COLORS = {
    -1: "rgba(0,100,0,0.4)",
    0: "rgba(0,180,0,0.3)",
    1: "rgba(255,255,0,0.3)",
    2: "rgba(255,180,0,0.3)",
    3: "rgba(255,100,0,0.3)",
    4: "rgba(255,50,0,0.3)",
    5: "rgba(180,0,0,0.3)",
}


def _hole_hue(i: int) -> int:
    return HOLE_HUES[i % len(HOLE_HUES)]


def _hex_to_rgb(h: str) -> dict | None:
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        return None
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}


def _rgb_to_hsl(r: int, g: int, b: int) -> dict:
    r, g, b = r / 255, g / 255, b / 255
    mx, mn = max(r, g, b), min(r, g, b)
    h = s = 0.0
    l = (mx + mn) / 2
    if mx != mn:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = ((g - b) / d + (6 if g < b else 0)) * 60
        elif mx == g:
            h = ((b - r) / d + 2) * 60
        else:
            h = ((r - g) / d + 4) * 60
    return {"h": h, "s": s, "l": l}


def _hsl_to_rgb(h: float, s: float, l: float) -> dict:
    h /= 360
    if s == 0:
        v = round(l * 255)
        return {"r": v, "g": v, "b": v}

    def f(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return {
        "r": round(f(p, q, h + 1 / 3) * 255),
        "g": round(f(p, q, h) * 255),
        "b": round(f(p, q, h - 1 / 3) * 255),
    }


def _tint_color(hex_color: str, hue: int, amt: float) -> str:
    if not hex_color or hex_color == "none" or hex_color.startswith("rgba"):
        return hex_color
    rgb = _hex_to_rgb(hex_color)
    if not rgb:
        return hex_color
    hsl = _rgb_to_hsl(rgb["r"], rgb["g"], rgb["b"])
    nh = hsl["h"] + (hue - hsl["h"]) * amt
    nr = _hsl_to_rgb(((nh % 360) + 360) % 360, hsl["s"], hsl["l"])
    return f"rgb({nr['r']},{nr['g']},{nr['b']})"


def _ff(n: float) -> str:
    return f"{n:.1f}"


def _esc_xml(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _coords_to_path(coords: list[list[float]], closed: bool = True) -> str:
    if not coords or len(coords) < 2:
        return ""
    d = f"M{_ff(coords[0][0])},{_ff(coords[0][1])}"
    for i in range(1, len(coords)):
        d += f"L{_ff(coords[i][0])},{_ff(coords[i][1])}"
    if closed:
        d += "Z"
    return d


def _build_text_paths(template: dict) -> str:
    inner_r = template["inner_r"]
    outer_r = template["outer_r"]
    sector_angle = template["sector_angle"]
    half_a = sector_angle / 2
    svg = ""
    offsets = [0.04, 0.055, 0.07]
    for i in range(3):
        angle = -half_a + offsets[i]
        svg += (
            f'<path id="textArc{i + 1}" d="M {_ff(inner_r * math.sin(angle))} '
            f'{_ff(-inner_r * math.cos(angle))} L {_ff(outer_r * math.sin(angle))} '
            f'{_ff(-outer_r * math.cos(angle))}" fill="none"/>'
        )
    return svg


def _render_ruler(zones_by_hole: list[dict], draw_area: dict, opts: dict, font_family: str) -> str:
    """Render vertical ruler — two-column design.

    LEFT column: hole numbers spanning full section height, rotated 90°,
                 alternating white-filled/outline rectangles.
    RIGHT column: score labels for each zone with alternating fills.
    """
    right_edge = draw_area.get("right", 870)
    hole_col_w = 12    # hole number column width
    score_col_w = 14   # score column width
    col_gap = 2
    total_w = hole_col_w + col_gap + score_col_w
    start_x = right_edge - total_w - 2

    hole_x = start_x
    score_x = start_x + hole_col_w + col_gap
    score_cx = score_x + score_col_w / 2

    svg = '<g class="layer-ruler">'

    # Pre-compute adjusted zone positions with gaps between holes
    # This ensures scores from adjacent holes don't overlap
    hole_gap = 3  # pixels between holes on the ruler
    if len(zones_by_hole) > 1:
        for hi in range(1, len(zones_by_hole)):
            prev_zones = zones_by_hole[hi - 1].get("zones", [])
            curr_zones = zones_by_hole[hi].get("zones", [])
            if prev_zones and curr_zones:
                prev_bottom = prev_zones[-1]["y_bottom"]
                curr_top = curr_zones[0]["y_top"]
                if curr_top - prev_bottom < hole_gap:
                    # Push current hole's zones down by the overlap amount
                    shift = hole_gap - (curr_top - prev_bottom)
                    for zone in curr_zones:
                        zone["_ruler_y_top"] = zone["y_top"] + shift
                        zone["_ruler_y_bottom"] = zone["y_bottom"] + shift

    # Mark zones that don't have adjusted positions
    for zone_result in zones_by_hole:
        for zone in zone_result.get("zones", []):
            if "_ruler_y_top" not in zone:
                zone["_ruler_y_top"] = zone["y_top"]
                zone["_ruler_y_bottom"] = zone["y_bottom"]

    for hi, zone_result in enumerate(zones_by_hole):
        hole_ref = zone_result.get("hole_ref", "")
        zones = zone_result.get("zones", [])
        if not zones:
            continue

        section_top = zones[0].get("_ruler_y_top", zones[0]["y_top"])
        section_bottom = zones[-1].get("_ruler_y_bottom", zones[-1]["y_bottom"])
        section_h = section_bottom - section_top
        is_odd = (hole_ref % 2 == 1) if isinstance(hole_ref, int) else True

        # --- Hole number rect spanning FULL section height ---
        hole_font = min(8, max(4, section_h * 0.12))
        if is_odd:
            svg += (
                f'<rect x="{_ff(hole_x)}" y="{_ff(section_top)}" '
                f'width="{_ff(hole_col_w)}" height="{_ff(section_h)}" rx="1.5" '
                f'fill="white" stroke="none" opacity="1"/>'
            )
            hcx = hole_x + hole_col_w / 2
            hcy = section_top + section_h / 2
            svg += (
                f'<text x="{_ff(hcx)}" y="{_ff(hcy)}" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'fill="#1a1a1a" font-size="{_ff(hole_font)}" font-weight="700" '
                f'font-family="{font_family}" '
                f'transform="rotate(-90, {_ff(hcx)}, {_ff(hcy)})">{hole_ref}</text>'
            )
        else:
            svg += (
                f'<rect x="{_ff(hole_x)}" y="{_ff(section_top)}" '
                f'width="{_ff(hole_col_w)}" height="{_ff(section_h)}" rx="1.5" '
                f'fill="none" stroke="white" stroke-width="0.5" opacity="1"/>'
            )
            hcx = hole_x + hole_col_w / 2
            hcy = section_top + section_h / 2
            svg += (
                f'<text x="{_ff(hcx)}" y="{_ff(hcy)}" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'fill="white" font-size="{_ff(hole_font)}" font-weight="700" '
                f'font-family="{font_family}" '
                f'transform="rotate(-90, {_ff(hcx)}, {_ff(hcy)})">{hole_ref}</text>'
            )

        # --- Score rects in separate column ---
        for zone in zones:
            label = zone["label"]
            score = zone.get("score", 0)
            zt = zone.get("_ruler_y_top", zone["y_top"])
            zb = zone.get("_ruler_y_bottom", zone["y_bottom"])
            zh = zb - zt
            y_mid = (zt + zb) / 2

            if zh < 1:
                continue

            # Adaptive font: scale to fit zone height, max 7, min 3
            label_font = min(7, max(3, zh * 0.7))

            is_odd_score = score in (1, 3, 5)
            if is_odd_score:
                svg += (
                    f'<rect x="{_ff(score_x)}" y="{_ff(zt)}" '
                    f'width="{_ff(score_col_w)}" height="{_ff(zh)}" '
                    f'fill="white" stroke="none" opacity="1"/>'
                )
                if zh >= 4:  # only render text if zone tall enough
                    svg += (
                        f'<text x="{_ff(score_cx)}" y="{_ff(y_mid + label_font * 0.35)}" '
                        f'text-anchor="middle" fill="#1a1a1a" font-size="{_ff(label_font)}" font-weight="700" '
                        f'font-family="{font_family}">{_esc_xml(label)}</text>'
                    )
            else:
                svg += (
                    f'<rect x="{_ff(score_x)}" y="{_ff(zt)}" '
                    f'width="{_ff(score_col_w)}" height="{_ff(zh)}" '
                    f'fill="none" stroke="white" stroke-width="0.5" opacity="1"/>'
                )
                if zh >= 4:
                    svg += (
                        f'<text x="{_ff(score_cx)}" y="{_ff(y_mid + label_font * 0.35)}" '
                        f'text-anchor="middle" fill="white" font-size="{_ff(label_font)}" '
                        f'font-family="{font_family}" opacity="0.7">{_esc_xml(label)}</text>'
                    )

    svg += "</g>"
    return svg



def _render_terrain_zones(terrain_zones: list, opts: dict, font_family: str,
                          vinyl_mode: bool = False) -> str:
    """Render terrain-following zones as polygon boundaries with score labels.

    In vinyl_mode: white strokes on dark background.
    Otherwise (scoring-preview): colored fills.
    """
    if not terrain_zones:
        return ""

    # Color map for scoring preview
    _PREVIEW_COLORS = {
        -1: "rgba(0,100,0,0.4)",
        0: "rgba(0,180,0,0.3)",
        1: "rgba(255,255,0,0.3)",
        2: "rgba(255,180,0,0.3)",
        3: "rgba(255,100,0,0.3)",
        4: "rgba(255,50,0,0.3)",
        5: "rgba(180,0,0,0.3)",
    }

    svg = '<g class="layer-terrain_zones">'
    for hole_tzs in terrain_zones:
        for tz in hole_tzs:
            poly = tz.get("polygon") or tz.get("contour", [])
            score = tz.get("score", 0)
            if not poly or len(poly) < 3:
                continue

            # Build path
            d = f"M{_ff(poly[0][0])},{_ff(poly[0][1])}"
            for pt in poly[1:]:
                d += f"L{_ff(pt[0])},{_ff(pt[1])}"
            d += "Z"

            if vinyl_mode:
                svg += (
                    f'<path d="{d}" fill="none" stroke="#ffffff" '
                    f'stroke-width="0.4" opacity="0.5"/>'
                )
            else:
                color = _PREVIEW_COLORS.get(score, "rgba(128,128,128,0.2)")
                svg += (
                    f'<path d="{d}" fill="{color}" stroke="none" opacity="1"/>'
                )

            # Score label
            lp = tz.get("label_position")
            if lp:
                lx = lp.get("x", 0)
                ly = lp.get("y", 0)
                label = f"{score:+d}" if score != 0 else "0"
                fill = "#ffffff" if vinyl_mode else "#000000"
                opacity = "0.9" if vinyl_mode else "0.8"
                zone_h = lp.get("zone_h", 6)
                zone_w = lp.get("zone_w", 6)
                fs = max(1.5, min(3, min(zone_h, zone_w) * 0.25))
                # Add a dark halo behind white text for readability
                if vinyl_mode:
                    svg += (
                        f'<text x="{_ff(lx)}" y="{_ff(ly)}" text-anchor="middle" '
                        f'dominant-baseline="central" '
                        f'fill="#000000" font-size="{fs}" font-weight="700" '
                        f'font-family="{font_family}" opacity="0.6" '
                        f'stroke="#000000" stroke-width="2">{label}</text>'
                    )
                svg += (
                    f'<text x="{_ff(lx)}" y="{_ff(ly)}" text-anchor="middle" '
                    f'dominant-baseline="central" '
                    f'fill="{fill}" font-size="{fs}" font-weight="700" '
                    f'font-family="{font_family}" opacity="{opacity}">{label}</text>'
                )

                # Leader line for small zones
                leader = tz.get("leader_line")
                if leader and len(leader) == 2:
                    stroke = "#ffffff" if vinyl_mode else "#666666"
                    svg += (
                        f'<line x1="{_ff(leader[0][0])}" y1="{_ff(leader[0][1])}" '
                        f'x2="{_ff(leader[1][0])}" y2="{_ff(leader[1][1])}" '
                        f'stroke="{stroke}" stroke-width="0.3" stroke-dasharray="1,1" '
                        f'opacity="0.6"/>'
                    )

    svg += "</g>"
    return svg


def _render_hole_stats(hole: dict, opts: dict, font_family: str) -> str:
    """Render hole number circle + stats in one combined box.

    The circle is at the top of the box, stats text below it.
    A dotted line connects the bottom of the box to the tee.

    ┌─────────┐
    │   (3)   │
    │  Par 4  │
    │ 483 yd  │
    │  HCP 7  │
    └─────────┘
         :      ← dotted line to tee
       [tee]
    """
    lines = []
    if hole.get("par"):
        lines.append(f"Par {hole['par']}")
    if hole.get("yardage"):
        lines.append(f"{hole['yardage']} yd")
    if hole.get("handicap"):
        lines.append(f"HCP {hole['handicap']}")

    is_warped = opts.get("vinyl_preview") and opts.get("is_warped")
    cr = 2.5 if is_warped else 3.5
    font_size = 1.8 if is_warped else 2.8
    num_font = 2.5 if is_warped else 3.5
    line_height = font_size + 0.8
    padding_x = 1.2
    padding_y = 1
    box_w = 13 if is_warped else 17

    # Box height: circle area + gap + text lines
    circle_area = cr * 2 + 1.5  # diameter + small gap below circle
    text_area = line_height * len(lines) if lines else 0
    box_h = padding_y + circle_area + text_area + padding_y

    # Position: BELOW the tee, offset to the tee side.
    # Tee is at the top of the hole. Box goes below (between tee and green).
    # For left-to-right holes: tee is on the LEFT, box offset left
    # For right-to-left holes: tee is on the RIGHT, box offset right
    tee_x = hole.get("start_x", 0)
    tee_y = hole.get("start_y", 0)
    direction = hole.get("direction", 1)

    # Offset box toward the tee side
    if direction > 0:
        box_cx = tee_x - box_w / 2 - 2  # left of tee
    else:
        box_cx = tee_x + box_w / 2 + 2  # right of tee

    box_x = box_cx - box_w / 2
    box_y = tee_y + 2  # below the tee

    svg = ""

    # Box outline
    svg += (
        f'<rect x="{_ff(box_x)}" y="{_ff(box_y)}" '
        f'width="{_ff(box_w)}" height="{_ff(box_h)}" rx="1" '
        f'fill="none" stroke="#ffffff" stroke-width="0.2" opacity="1"/>'
    )

    # Hole number circle at top of box — alternating style matching ruler
    circle_cy = box_y + padding_y + cr
    hole_ref = hole.get("ref", 0)
    is_odd = (hole_ref % 2 == 1) if isinstance(hole_ref, int) else True

    if is_odd:
        # White filled circle, dark number (matches white ruler badge)
        svg += (
            f'<circle cx="{_ff(box_cx)}" cy="{_ff(circle_cy)}" r="{cr}" '
            f'fill="white" stroke="none" opacity="1"/>'
        )
        svg += (
            f'<text x="{_ff(box_cx)}" y="{_ff(circle_cy + num_font * 0.38)}" text-anchor="middle" '
            f'fill="#1a1a1a" font-size="{num_font}" font-weight="700" '
            f'font-family="{font_family}" opacity="1">{hole_ref}</text>'
        )
    else:
        # Outline circle, white number (matches outline ruler badge)
        svg += (
            f'<circle cx="{_ff(box_cx)}" cy="{_ff(circle_cy)}" r="{cr}" '
            f'fill="none" stroke="#ffffff" stroke-width="0.3" opacity="1"/>'
        )
        svg += (
            f'<text x="{_ff(box_cx)}" y="{_ff(circle_cy + num_font * 0.38)}" text-anchor="middle" '
            f'fill="#ffffff" font-size="{num_font}" font-weight="700" '
            f'font-family="{font_family}" opacity="1">{hole_ref}</text>'
        )

    # Stats text below circle
    text_start_y = circle_cy + cr + 1.5
    for i, line in enumerate(lines):
        ty = text_start_y + (i + 0.7) * line_height
        svg += (
            f'<text x="{_ff(box_cx)}" y="{_ff(ty)}" '
            f'text-anchor="middle" fill="white" font-size="{font_size}" '
            f'font-family="{font_family}" opacity="1">{_esc_xml(line)}</text>'
        )

    # Dotted line from tee down to top of box
    svg += (
        f'<line x1="{_ff(tee_x)}" y1="{_ff(tee_y)}" '
        f'x2="{_ff(box_cx)}" y2="{_ff(box_y)}" '
        f'stroke="#ffffff" stroke-dasharray="1.5,1" stroke-width="0.3" opacity="1"/>'
    )

    return svg


def _render_scoring_preview(holes: list[dict], zones_by_hole: list[dict],
                             draw_area: dict, font_family: str) -> str:
    """Render colored scoring zone bands for preview/testing mode."""
    canvas_width = draw_area.get("right", 870) - draw_area.get("left", 60)
    left = draw_area.get("left", 60)

    svg = '<g class="layer-scoring_preview">'
    for zone_result in zones_by_hole:
        for zone in zone_result.get("zones", []):
            color = ZONE_COLORS.get(zone["score"], "rgba(128,128,128,0.2)")
            y_top = zone["y_top"]
            y_bottom = zone["y_bottom"]
            height = y_bottom - y_top
            if height <= 0:
                continue
            svg += (
                f'<rect x="{_ff(left)}" y="{_ff(y_top)}" '
                f'width="{_ff(canvas_width)}" height="{_ff(height)}" '
                f'fill="{color}"/>'
            )
            # Zone label centered in band
            mid_y = (y_top + y_bottom) / 2
            svg += (
                f'<text x="{_ff(left + canvas_width / 2)}" y="{_ff(mid_y + 2)}" '
                f'text-anchor="middle" fill="white" font-size="4" '
                f'font-family="{font_family}" opacity="0.7">{_esc_xml(zone["label"])}</text>'
            )
    svg += "</g>"
    return svg


def _render_vinyl_preview(layout: dict, opts: dict, layer: str = "all") -> str:
    """Render vinyl-preview mode, optionally filtered to a single color layer.

    layer="all"   → full glass preview (background + all colors)
    layer="white"  → only white elements, no background (cricut white)
    layer="green"  → only green elements (cricut green)
    layer="blue"   → only blue elements (cricut blue)
    layer="tan"    → only tan elements (cricut tan)
    """
    font_family = opts.get("font_family", "'Arial', sans-serif")
    holes = layout.get("holes", [])
    is_warped = layout.get("warped") and layout.get("template")
    zones_by_hole = opts.get("zones_by_hole", [])
    terrain_zones = opts.get("terrain_zones", [])

    # Make warp info available to sub-renderers
    if is_warped:
        opts["_template"] = layout["template"]
        opts["is_warped"] = True

    # Pass canvas width for stats boundary checking
    opts["_canvas_width"] = layout.get("canvas_width", 900)

    # Layer flags
    _all = layer == "all"
    _white = layer in ("all", "white")
    _green = layer in ("all", "green")
    _blue = layer in ("all", "blue")
    _tan = layer in ("all", "tan")

    if is_warped:
        t = layout["template"]
        half_a = t["sector_angle"] / 2
        pad = 8
        vb_x = -t["outer_r"] * math.sin(half_a) - pad
        vb_y = -t["outer_r"] - pad
        vb_w = 2 * t["outer_r"] * math.sin(half_a) + pad * 2
        vb_h = t["outer_r"] - t["inner_r"] * math.cos(half_a) + pad * 2
    else:
        vb_x, vb_y = 0, 0
        vb_w = layout.get("canvas_width", 900)
        vb_h = layout.get("canvas_height", 700)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{_ff(vb_x)} {_ff(vb_y)} {_ff(vb_w)} {_ff(vb_h)}" '
        f'width="{round(vb_w)}" height="{round(vb_h)}">'
    )

    # Defs: clip path (no gradient — solid dark background represents glass)
    svg += "<defs>"
    if is_warped:
        from app.services.render.glass_template import glass_wrap_path
        svg += f'<clipPath id="glassClip"><path d="{glass_wrap_path(layout["template"])}"/></clipPath>'
        svg += _build_text_paths(layout["template"])
    svg += "</defs>"

    # Background — only for full preview, not individual layers
    _BG_COLOR = "#1a1a1a"
    if is_warped:
        from app.services.render.glass_template import glass_wrap_path
        svg += '<g clip-path="url(#glassClip)">'
        if _all:
            svg += f'<path d="{glass_wrap_path(layout["template"])}" fill="{_BG_COLOR}"/>'
    else:
        if _all:
            svg += (
                f'<rect x="0" y="0" width="{layout.get("canvas_width", 900)}" '
                f'height="{layout.get("canvas_height", 700)}" fill="{_BG_COLOR}" rx="4"/>'
            )

    # Terrain-following zone contours — DISABLED in vinyl/glass preview.
    # These produce visual artifacts (concentric shapes, horizontal lines)
    # that do not represent what's actually printed on the glass.
    # Scoring elements (zone_line, zone_label) are now synthetic features
    # injected in rect space before warping. Collect them from the warped layout
    # for knockout masks and visible rendering.

    _WHITE_CATS = {"rough", "path", "course_boundary"}
    _GREEN_FILL_CATS = {"fairway"}
    _GREEN_CATS = {"green", "tee"}
    _BLUE_CATS = {"water"}

    # Collect knockout info from warped features
    _knockout_labels = []       # score text knockouts (green -1 + zone_label)
    _knockout_green_paths = []  # green polygon paths
    _knockout_zone_lines = []   # zone boundary polylines
    _external_labels = []       # reserved for future use

    for hole in holes:
        for f in hole.get("features", []):
            cat = f.get("category", "")
            coords = f.get("coords", [])

            if cat == "green" and len(coords) >= 3:
                gx = sum(p[0] for p in coords) / len(coords)
                gy = sum(p[1] for p in coords) / len(coords)
                _knockout_labels.append({"x": gx, "y": gy, "label": "-1", "font_size": 3})
                gd = _coords_to_path(coords, closed=True)
                if gd:
                    _knockout_green_paths.append(gd)

            elif cat == "zone_line" and len(coords) >= 2:
                _knockout_zone_lines.append({"coords": coords})

            elif cat == "zone_label" and coords:
                _knockout_labels.append({
                    "x": coords[0][0],
                    "y": coords[0][1],
                    "label": f.get("label", ""),
                    "font_size": f.get("font_size", 2),
                    "feature_cat": f.get("feature_cat"),
                })

            elif cat == "zone_label_external" and len(coords) >= 2:
                _external_labels.append({
                    "x": coords[0][0],
                    "y": coords[0][1],
                    "anchor_x": coords[1][0],
                    "anchor_y": coords[1][1],
                    "label": f.get("label", ""),
                    "font_size": f.get("font_size", 1.8),
                })

    svg += '<g class="layer-vinyl_features">'

    # Render features in z-order: rough, water, fairway, bunker, tee, green
    # Only render ONE green outline + flag per hole to avoid concentric rings
    _RENDER_ORDER = ["rough", "path", "course_boundary", "water", "fairway", "bunker", "tee", "green", "zone_line"]
    _filled_idx = 0
    _green_rendered = set()  # track which holes already have a green rendered
    for hole in holes:
        feats = hole.get("features", [])
        sorted_feats = sorted(feats, key=lambda f: _RENDER_ORDER.index(f.get("category", "")) if f.get("category", "") in _RENDER_ORDER else 99)
        _hole_id = id(hole)
        for feat in sorted_feats:
            cat = feat.get("category", "")
            d = _coords_to_path(feat.get("coords", []), cat != "path")
            if not d:
                continue

            if cat in _WHITE_CATS and _white:
                svg += (
                    f'<path d="{d}" fill="none" stroke="#ffffff" '
                    f'stroke-width="0.15" opacity="1"/>'
                )
            elif cat in _GREEN_FILL_CATS and _green:
                # Solid green fill with green polygon + score text knocked out.
                # Green interiors become transparent (bare glass = dark background).
                mid = f"fwMask{_filled_idx}"
                has_knockouts = _knockout_green_paths or _knockout_zone_lines or _knockout_labels
                if has_knockouts:
                    svg += f'<mask id="{mid}"><rect x="-9999" y="-9999" width="99999" height="99999" fill="white"/>'
                    # Cut out green polygon shapes
                    for gpath in _knockout_green_paths:
                        svg += f'<path d="{gpath}" fill="black"/>'
                    # Cut out zone boundary lines (warped polylines)
                    for zl in _knockout_zone_lines:
                        zd = _coords_to_path(zl["coords"], closed=False)
                        if zd:
                            svg += f'<path d="{zd}" fill="none" stroke="black" stroke-width="0.2"/>'
                    # Cut out score number text
                    for kl in _knockout_labels:
                        kfs = kl.get("font_size", 3)
                        svg += (
                            f'<text x="{_ff(kl["x"])}" y="{_ff(kl["y"])}" text-anchor="middle" '
                            f'dominant-baseline="central" '
                            f'fill="black" font-size="{_ff(kfs)}" font-weight="700" '
                            f'font-family="{font_family}">{kl["label"]}</text>'
                        )
                    svg += '</mask>'
                    svg += (
                        f'<path d="{d}" fill="#4ade80" stroke="#4ade80" '
                        f'stroke-width="0.2" opacity="1" mask="url(#{mid})"/>'
                    )
                else:
                    svg += (
                        f'<path d="{d}" fill="#4ade80" stroke="#4ade80" '
                        f'stroke-width="0.2" opacity="1"/>'
                    )
                _filled_idx += 1
            elif cat in _GREEN_CATS and _green:
                # For greens: only render ONE outline + flag per hole
                if cat == "green" and _hole_id in _green_rendered:
                    continue
                if cat == "green":
                    _green_rendered.add(_hole_id)
                sw = "0.15" if cat == "tee" else "0.2"
                svg += (
                    f'<path d="{d}" fill="none" stroke="#4ade80" '
                    f'stroke-width="{sw}" opacity="1"/>'
                )
                # Flag marker inside green (no circle — just flag pole + triangle)
                if cat == "green" and feat.get("coords"):
                    coords = feat["coords"]
                    gx = sum(p[0] for p in coords) / len(coords)
                    gy = sum(p[1] for p in coords) / len(coords)
                    # Small flag pole + triangle
                    svg += (
                        f'<line x1="{_ff(gx)}" y1="{_ff(gy)}" '
                        f'x2="{_ff(gx)}" y2="{_ff(gy - 2.5)}" '
                        f'stroke="#ffffff" stroke-width="0.2" opacity="1"/>'
                    )
                    svg += (
                        f'<path d="M{_ff(gx)},{_ff(gy - 2.5)}L{_ff(gx + 1.5)},{_ff(gy - 1.8)}'
                        f'L{_ff(gx)},{_ff(gy - 1.2)}Z" '
                        f'fill="#ffffff" opacity="1"/>'
                    )
            elif cat in _BLUE_CATS and _blue:
                # Solid blue fill with zone lines + score knockouts
                mid = f"wtMask{_filled_idx}"
                has_water_ko = _knockout_labels or _knockout_zone_lines
                if has_water_ko:
                    svg += f'<mask id="{mid}"><rect x="-9999" y="-9999" width="99999" height="99999" fill="white"/>'
                    # Zone boundary lines (warped polylines)
                    for zl in _knockout_zone_lines:
                        zd = _coords_to_path(zl["coords"], closed=False)
                        if zd:
                            svg += f'<path d="{zd}" fill="none" stroke="black" stroke-width="0.2"/>'
                    # Score number knockouts
                    for kl in _knockout_labels:
                        kfs = kl.get("font_size", 3)
                        svg += (
                            f'<text x="{_ff(kl["x"])}" y="{_ff(kl["y"])}" text-anchor="middle" '
                            f'dominant-baseline="central" '
                            f'fill="black" font-size="{_ff(kfs)}" font-weight="700" '
                            f'font-family="{font_family}">{kl["label"]}</text>'
                        )
                    svg += '</mask>'
                    svg += (
                        f'<path d="{d}" fill="#3b82f6" stroke="#3b82f6" '
                        f'stroke-width="0.2" opacity="1" mask="url(#{mid})"/>'
                    )
                else:
                    svg += (
                        f'<path d="{d}" fill="#3b82f6" stroke="#3b82f6" '
                        f'stroke-width="0.2" opacity="1"/>'
                    )
                _filled_idx += 1
            elif cat == "bunker" and _tan:
                svg += (
                    f'<path d="{d}" fill="#d2b48c" stroke="#d2b48c" '
                    f'stroke-width="0.2" opacity="1"/>'
                )
            elif cat in ("zone_line", "zone_label", "zone_label_external"):
                continue  # only used in knockout masks / external labels, not rendered as visible elements
    svg += "</g>"

    # External zone labels (white text + dashed leader line for small zones)
    if _white and _external_labels:
        svg += '<g class="layer-external_zone_labels">'
        for el in _external_labels:
            efs = el["font_size"]
            svg += (
                f'<line x1="{_ff(el["x"])}" y1="{_ff(el["y"])}" '
                f'x2="{_ff(el["anchor_x"])}" y2="{_ff(el["anchor_y"])}" '
                f'stroke="#ffffff" stroke-width="0.15" stroke-dasharray="0.5,0.5" '
                f'opacity="0.7"/>'
            )
            svg += (
                f'<text x="{_ff(el["x"])}" y="{_ff(el["y"])}" text-anchor="middle" '
                f'dominant-baseline="central" '
                f'fill="#ffffff" font-size="{_ff(efs)}" font-weight="700" '
                f'font-family="{font_family}" opacity="0.9">{el["label"]}</text>'
            )
        svg += '</g>'

    # White elements: hole number + stats combined boxes, ruler, text, logo, QR
    if _white:
        # Combined hole number + stats boxes (circle inside box, dotted line to tee)
        svg += '<g class="layer-hole_stats">'
        for hole in holes:
            svg += _render_hole_stats(hole, opts, font_family)
        svg += "</g>"

        # Ruler
        draw_area = layout.get("draw_area", {
            "left": 60, "right": layout.get("canvas_width", 900) - 30,
            "top": 30, "bottom": layout.get("canvas_height", 700) - 30,
        })
        if zones_by_hole:
            if is_warped:
                svg += _render_ruler_warped(zones_by_hole, layout, opts, font_family)
            else:
                svg += _render_ruler(zones_by_hole, draw_area, opts, font_family)

    if is_warped:
        svg += "</g>"  # close clip group
        # Glass outline as a cut guide (visible stroke)
        from app.services.render.glass_template import glass_wrap_path as _gwp2
        svg += (
            f'<path d="{_gwp2(layout["template"])}" fill="none" '
            f'stroke="#ffffff" stroke-width="0.3" opacity="1"/>'
        )

    if _white:
        # Course name + hole range
        if opts.get("course_name") or opts.get("hole_range") or opts.get("logo_data_url"):
            if is_warped:
                svg += _render_warped_text(layout, opts, font_family)
            else:
                svg += _render_rect_text(layout, opts, font_family)

        # Logo at bottom-left
        if opts.get("logo_data_url"):
            svg += _render_logo_bottom_left(layout, opts)

        # QR code
        if opts.get("qr_svg"):
            svg += _render_embedded_qr(layout, opts, font_family)

    # Debug overlay: red arcs at each zone boundary following glass curvature.
    if opts.get("show_score_lines") and zones_by_hole:
        svg += '<g class="layer-debug-score-lines">'

        # Use the warped zone_line features directly — they went through
        # the same warp_pt() as all other features, so they're at the
        # correct positions. Extend each polyline to span the full glass width.
        if is_warped:
            tmpl = layout.get("template", {})
            half_a = tmpl.get("sector_angle", 1) / 2

            # Collect zone_line features with their labels, grouped by hole
            for hi, hole in enumerate(holes):
                if hi >= len(zones_by_hole):
                    continue
                zone_result = zones_by_hole[hi]
                above = [z for z in zone_result.get("zones", []) if z.get("position") != "below"]
                label_idx = 0

                for f in hole.get("features", []):
                    if f.get("category") != "zone_line":
                        continue
                    coords = f.get("coords", [])
                    if len(coords) < 2:
                        continue

                    # The zone_line is a warped polyline. To extend it across
                    # the full glass, compute the radius at the midpoint and
                    # draw an arc at that radius.
                    mid_pt = coords[len(coords) // 2]
                    r = (mid_pt[0] ** 2 + mid_pt[1] ** 2) ** 0.5
                    large_arc = 1 if half_a * 2 > math.pi else 0
                    x1 = -r * math.sin(half_a)
                    y1 = -r * math.cos(half_a)
                    x2 = r * math.sin(half_a)
                    y2 = -r * math.cos(half_a)
                    svg += (
                        f'<path d="M{_ff(x1)},{_ff(y1)} A{_ff(r)},{_ff(r)} 0 {large_arc} 1 {_ff(x2)},{_ff(y2)}" '
                        f'fill="none" stroke="#ff0000" stroke-width="0.3" opacity="0.6"/>'
                    )

                    # Label
                    label = f.get("label", "")
                    lx = r * math.sin(half_a) + 2
                    ly = -r * math.cos(half_a)
                    svg += (
                        f'<text x="{_ff(lx)}" y="{_ff(ly + 0.8)}" '
                        f'text-anchor="start" fill="#ff0000" font-size="2" '
                        f'font-weight="700" font-family="Arial">{_esc_xml(label)}</text>'
                    )
        else:
            # Rect mode: full-width horizontal lines
            cw = layout.get("canvas_width", 900)
            for hi, zone_result in enumerate(zones_by_hole):
                if hi >= len(holes):
                    continue
                hole = holes[hi]
                above = [z for z in zone_result.get("zones", []) if z.get("position") != "below"]
                total = len(above)
                if total < 1:
                    continue
                for zi in range(total + 1):
                    tt = zi / total
                    line_y = hole["start_y"] + tt * (hole["end_y"] - hole["start_y"])
                    svg += (
                        f'<line x1="0" y1="{_ff(line_y)}" x2="{cw}" y2="{_ff(line_y)}" '
                        f'stroke="#ff0000" stroke-width="0.4" opacity="0.6"/>'
                    )
                    if zi < total:
                        label = above[zi]["label"]
                        mid_y = line_y  # label at top of zone (same as the line)
                        svg += (
                            f'<text x="{cw - 2}" y="{_ff(mid_y + 1)}" '
                            f'text-anchor="end" fill="#ff0000" font-size="3" '
                            f'font-weight="700" font-family="Arial">{_esc_xml(label)}</text>'
                        )
        svg += "</g>"

    svg += "</svg>"
    return svg


def _render_ruler_warped(zones_by_hole: list[dict], layout: dict,
                         opts: dict, font_family: str) -> str:
    """Render ruler on glass sector — two-column design following curvature.

    In rotated coordinate space (rotated by edge_angle around origin):
    - y-axis is radial (negative = outward toward outer_r)
    - x-axis is tangential (negative = inside glass, positive = outside)

    Both columns placed at NEGATIVE x (inside glass).
    SCORE column is closer to edge (less negative x).
    HOLE column is further inside (more negative x).
    """
    t = layout.get("template", {})
    if not t:
        return ""
    half_a = t["sector_angle"] / 2
    inner_r = t["inner_r"]
    outer_r = t["outer_r"]
    edge_angle = half_a
    rot_deg = math.degrees(edge_angle)

    score_col_w = 7
    hole_col_w = 8
    col_gap = 2
    min_font = 2.5

    # Both columns INSIDE the glass (negative x in rotated frame)
    score_cx = -(score_col_w / 2 + 1)
    hole_cx = -(score_col_w + col_gap + hole_col_w / 2 + 1)

    # Use the SAME y→r conversion as warp_pt() if warp params are available.
    # This ensures ruler positions match the warped zone_line features exactly.
    warp_min_y = layout.get("_warp_min_y")
    warp_content_h = layout.get("_warp_content_h")
    warp_r_top = layout.get("_warp_r_top")
    warp_r_bot = layout.get("_warp_r_bot")

    if warp_min_y is not None and warp_content_h and warp_r_top is not None:
        def _y_to_r(y):
            ny = (y - warp_min_y) / warp_content_h
            return warp_r_top - ny * (warp_r_top - warp_r_bot)
    else:
        # Fallback to draw_area-based conversion
        draw_area = layout.get("draw_area", {})
        canvas_top = draw_area.get("top", 30)
        canvas_bottom = draw_area.get("bottom", 670)
        canvas_range = canvas_bottom - canvas_top or 1
        def _y_to_r(y):
            frac = (y - canvas_top) / canvas_range
            return outer_r - frac * (outer_r - inner_r)

    svg = '<g class="layer-ruler">'

    # Render ruler using exact RAW zone positions. No clamping —
    # positions match the warped zone_line features and debug arcs exactly.
    for hi, zone_result in enumerate(zones_by_hole):
        hole_ref = zone_result.get("hole_ref", "")
        zones = zone_result.get("zones", [])
        if not zones:
            continue

        section_r_top = _y_to_r(zones[0]["y_top"])
        section_r_bot = _y_to_r(zones[-1]["y_bottom"])
        total_section = abs(section_r_top - section_r_bot)

        if total_section < 3:
            continue

        is_odd = (hole_ref % 2 == 1) if isinstance(hole_ref, int) else True

        # Hole number rect: spans FULL adjusted section height
        hn_h = total_section
        ry_top = -section_r_top

        svg += f'<g transform="rotate({_ff(rot_deg)}, 0, 0)">'

        if is_odd:
            svg += (
                f'<rect x="{_ff(hole_cx - hole_col_w / 2)}" y="{_ff(ry_top)}" '
                f'width="{_ff(hole_col_w)}" height="{_ff(hn_h)}" rx="1.5" '
                f'fill="white" stroke="none" opacity="1"/>'
            )
            text_cy = ry_top + hn_h / 2
            fs = min(5, max(min_font, hn_h * 0.6))
            svg += (
                f'<text x="{_ff(hole_cx)}" y="{_ff(text_cy)}" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'fill="#1a1a1a" font-size="{_ff(fs)}" font-weight="700" '
                f'font-family="{font_family}" '
                f'transform="rotate(-90, {_ff(hole_cx)}, {_ff(text_cy)})">{hole_ref}</text>'
            )
        else:
            svg += (
                f'<rect x="{_ff(hole_cx - hole_col_w / 2)}" y="{_ff(ry_top)}" '
                f'width="{_ff(hole_col_w)}" height="{_ff(hn_h)}" rx="1.5" '
                f'fill="none" stroke="white" stroke-width="0.5" opacity="1"/>'
            )
            text_cy = ry_top + hn_h / 2
            fs = min(5, max(min_font, hn_h * 0.6))
            svg += (
                f'<text x="{_ff(hole_cx)}" y="{_ff(text_cy)}" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'fill="white" font-size="{_ff(fs)}" font-weight="700" '
                f'font-family="{font_family}" '
                f'transform="rotate(-90, {_ff(hole_cx)}, {_ff(text_cy)})">{hole_ref}</text>'
            )

        svg += '</g>'

        # Score rects at RAW zone positions — no proportional redistribution.
        # Each zone renders at its exact _y_to_r(y_top) to _y_to_r(y_bottom).
        sx = score_cx - score_col_w / 2
        sw = score_col_w

        # Pre-compute zone edges directly from zone boundaries
        zone_edges = []
        for zone in zones:
            zone_edges.append(_y_to_r(zone["y_top"]))
        zone_edges.append(_y_to_r(zones[-1]["y_bottom"]))

        svg += f'<g transform="rotate({_ff(rot_deg)}, 0, 0)">'

        # Step 1: Draw ONE white background rect for the entire score column
        score_total = abs(zone_edges[0] - zone_edges[-1])
        svg += (
            f'<rect x="{_ff(sx)}" y="{_ff(-zone_edges[0])}" '
            f'width="{_ff(sw)}" height="{_ff(score_total)}" '
            f'fill="white" stroke="none"/>'
        )

        # Step 2: Draw dark rects for "even" zones (0, -1, +2, +4)
        # These punch through the white background to show dark
        for zi, zone in enumerate(zones):
            score = zone.get("score", 0)
            is_odd_score = score in (1, 3, 5)
            if is_odd_score:
                continue  # stays white

            r_t = zone_edges[zi]
            r_b = zone_edges[zi + 1]
            zone_r = abs(r_t - r_b)
            if zone_r < 0.2:
                continue

            svg += (
                f'<rect x="{_ff(sx)}" y="{_ff(-r_t)}" '
                f'width="{_ff(sw)}" height="{_ff(zone_r)}" '
                f'fill="#1a1a1a" stroke="none"/>'
            )

        # Step 3: Draw thin white outline around the entire column
        svg += (
            f'<rect x="{_ff(sx)}" y="{_ff(-zone_edges[0])}" '
            f'width="{_ff(sw)}" height="{_ff(score_total)}" '
            f'fill="none" stroke="white" stroke-width="0.3"/>'
        )

        # Step 4: Draw horizontal divider lines at each zone edge
        for zi in range(1, len(zone_edges) - 1):
            ey = -zone_edges[zi]
            svg += (
                f'<line x1="{_ff(sx)}" y1="{_ff(ey)}" '
                f'x2="{_ff(sx + sw)}" y2="{_ff(ey)}" '
                f'stroke="white" stroke-width="0.2"/>'
            )

        # Step 5: Score labels
        for zi, zone in enumerate(zones):
            label = zone["label"]
            score = zone.get("score", 0)
            is_odd_score = score in (1, 3, 5)

            r_t = zone_edges[zi]
            r_b = zone_edges[zi + 1]
            zone_r = abs(r_t - r_b)
            if zone_r < 0.2:
                continue

            r_mid_y = -(r_t + r_b) / 2
            fs = min(3.5, max(1.2, zone_r * 0.6))
            # Never let text exceed zone height
            if fs > zone_r * 0.85:
                fs = zone_r * 0.85

            text_fill = "#1a1a1a" if is_odd_score else "white"
            svg += (
                f'<text x="{_ff(score_cx)}" y="{_ff(r_mid_y + fs * 0.35)}" '
                f'text-anchor="middle" fill="{text_fill}" font-size="{_ff(fs)}" font-weight="700" '
                f'font-family="{font_family}">{_esc_xml(label)}</text>'
            )

        svg += '</g>'

    svg += "</g>"
    return svg


def _render_logo_bottom_left(layout: dict, opts: dict) -> str:
    """Render logo at bottom-left of the layout."""
    logo_url = opts.get("logo_data_url")
    if not logo_url:
        return ""

    is_warped = layout.get("warped") and layout.get("template")

    if is_warped:
        t = layout["template"]
        half_a = t["sector_angle"] / 2
        r = t["inner_r"] + (t["outer_r"] - t["inner_r"]) * 0.1
        edge_angle = -half_a + 0.03
        cx = r * math.sin(edge_angle)
        cy = -r * math.cos(edge_angle)
        img_size = (t["outer_r"] - t["inner_r"]) * 0.06
        return (
            f'<image href="{_esc_xml(logo_url)}" '
            f'x="{_ff(cx - img_size / 2)}" y="{_ff(cy - img_size / 2)}" '
            f'width="{_ff(img_size)}" height="{_ff(img_size)}" '
            f'opacity="1" preserveAspectRatio="xMidYMid meet"/>'
        )
    else:
        ch = layout.get("canvas_height", 700)
        return (
            f'<image href="{_esc_xml(logo_url)}" '
            f'x="5" y="{_ff(ch - 25)}" width="20" height="20" '
            f'opacity="1" preserveAspectRatio="xMidYMid meet"/>'
        )


def render_svg(layout: dict, opts: dict | None = None) -> str:
    """Render SVG string from layout data."""
    opts = opts or {}

    # Vinyl preview mode uses a completely different rendering path
    if opts.get("vinyl_preview"):
        return _render_vinyl_preview(layout, opts)

    # Merge styles
    styles = {}
    for k, v in DEFAULT_STYLES.items():
        styles[k] = {**v, **(opts.get("styles", {}).get(k, {}))}

    hidden = set(opts.get("hidden_layers", []))
    per_hole_colors = opts.get("per_hole_colors", True)
    font_family = opts.get("font_family", "'Arial', sans-serif")
    holes = layout.get("holes", [])
    is_warped = layout.get("warped") and layout.get("template")
    zones_by_hole = opts.get("zones_by_hole", [])
    scoring_preview = opts.get("scoring_preview", False)

    if is_warped:
        t = layout["template"]
        half_a = t["sector_angle"] / 2
        pad = 8
        vb_x = -t["outer_r"] * math.sin(half_a) - pad
        vb_y = -t["outer_r"] - pad
        vb_w = 2 * t["outer_r"] * math.sin(half_a) + pad * 2
        vb_h = t["outer_r"] - t["inner_r"] * math.cos(half_a) + pad * 2
    else:
        vb_x, vb_y = 0, 0
        vb_w = layout.get("canvas_width", 900)
        vb_h = layout.get("canvas_height", 700)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{_ff(vb_x)} {_ff(vb_y)} {_ff(vb_w)} {_ff(vb_h)}" '
        f'width="{round(vb_w)}" height="{round(vb_h)}">'
    )

    svg += "<defs>"
    if is_warped:
        from app.services.render.glass_template import glass_wrap_path
        svg += f'<clipPath id="glassClip"><path d="{glass_wrap_path(layout["template"])}"/></clipPath>'
        svg += _build_text_paths(layout["template"])
    svg += "</defs>"

    if is_warped:
        from app.services.render.glass_template import glass_wrap_path
        svg += '<g clip-path="url(#glassClip)">'
        if "background" not in hidden:
            svg += f'<path d="{glass_wrap_path(layout["template"])}" fill="{styles["background"]["fill"]}"/>'
    else:
        if "background" not in hidden:
            svg += (
                f'<rect x="0" y="0" width="{layout.get("canvas_width", 900)}" '
                f'height="{layout.get("canvas_height", 700)}" fill="{styles["background"]["fill"]}" rx="4"/>'
            )

    # Scoring preview bands (rendered behind features)
    draw_area = layout.get("draw_area", {
        "left": 60, "right": layout.get("canvas_width", 900) - 30,
        "top": 30, "bottom": layout.get("canvas_height", 700) - 30,
    })
    if scoring_preview and zones_by_hole and not is_warped:
        svg += _render_scoring_preview(holes, zones_by_hole, draw_area, font_family)

    # Terrain-following zone overlays (scoring-preview mode)
    terrain_zones = opts.get("terrain_zones")
    if scoring_preview and terrain_zones and not is_warped:
        svg += _render_terrain_zones(terrain_zones, opts, font_family, vinyl_mode=False)

    # Feature layers
    for layer in FEATURE_LAYERS:
        if layer in hidden:
            continue
        s = styles.get(layer)
        if not s:
            continue
        tintable = layer in ("fairway", "rough", "tee", "green")
        svg += f'<g class="layer-{layer}">'
        for hi, hole in enumerate(holes):
            hue = _hole_hue(hi)
            for feat in hole.get("features", []):
                if feat.get("category") != layer:
                    continue
                d = _coords_to_path(feat.get("coords", []), layer != "path")
                if not d:
                    continue
                fill = s["fill"]
                stroke = s["stroke"]
                if per_hole_colors and tintable and fill != "none":
                    fill = _tint_color(fill, hue, 0.35)
                if per_hole_colors and tintable and stroke and stroke != "none":
                    stroke = _tint_color(stroke, hue, 0.25)
                svg += (
                    f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
                    f'stroke-width="{s["stroke_width"]}" opacity="{s["opacity"]}"/>'
                )
        svg += "</g>"

    # Scoring arcs removed — will be replaced by terrain-following zones

    # Hole numbers
    if "hole_number" not in hidden:
        s = styles["hole_number"]
        sz = 5 if is_warped else 6
        cr = 5 if is_warped else 6
        svg += '<g class="layer-hole_number">'
        for hole in holes:
            x_off = -(cr + 3) if hole.get("direction", 1) > 0 else (cr + 3)
            lx = hole["start_x"] + x_off
            ly = hole["start_y"] + cr + 4
            svg += (
                f'<circle cx="{_ff(lx)}" cy="{_ff(ly)}" r="{cr}" '
                f'fill="{s["fill"]}" stroke="{s["stroke"]}" '
                f'stroke-width="{s["stroke_width"]}" opacity="{s["opacity"]}"/>'
            )
            svg += (
                f'<text x="{_ff(lx)}" y="{_ff(ly + sz * 0.38)}" text-anchor="middle" '
                f'fill="white" font-size="{sz}" font-weight="700" '
                f'font-family="{font_family}">{hole.get("ref", "")}</text>'
            )
        svg += "</g>"

    # Par labels
    if "hole_par" not in hidden:
        s = styles["hole_par"]
        sz = 5 if is_warped else 6
        svg += '<g class="layer-hole_par">'
        for hole in holes:
            if not hole.get("par"):
                continue
            greens = [f for f in hole.get("features", []) if f.get("category") == "green"]
            if greens:
                gx = gy = 0.0
                n = 0
                for g in greens:
                    for x, y in g["coords"]:
                        gx += x
                        gy += y
                        n += 1
                lx = gx / n
                ly = gy / n + (4 if is_warped else 6)
            else:
                lx = hole["end_x"]
                ly = hole["end_y"] + (4 if is_warped else 6)
            svg += (
                f'<text x="{_ff(lx)}" y="{_ff(ly + 2)}" text-anchor="middle" '
                f'fill="{s["fill"]}" font-size="{sz * 0.75}" '
                f'font-family="{font_family}" opacity="{s["opacity"]}">P{hole["par"]}</text>'
            )
        svg += "</g>"

    # Hole stats
    if "hole_stats" not in hidden and holes:
        svg += '<g class="layer-hole_stats">'
        for hole in holes:
            svg += _render_hole_stats(hole, opts, font_family)
        svg += "</g>"

    # Ruler
    if "ruler" not in hidden and zones_by_hole and not is_warped:
        svg += _render_ruler(zones_by_hole, draw_area, opts, font_family)

    if is_warped:
        svg += "</g>"
        if opts.get("show_glass_outline", True):
            from app.services.render.glass_template import glass_wrap_path
            svg += (
                f'<path d="{glass_wrap_path(layout["template"])}" fill="none" '
                f'stroke="#555" stroke-width="0.5" stroke-dasharray="3,2"/>'
            )

    # Text overlays
    if opts.get("course_name") or opts.get("hole_range") or opts.get("logo_data_url"):
        if is_warped:
            svg += _render_warped_text(layout, opts, font_family)
        else:
            svg += _render_rect_text(layout, opts, font_family)

    # QR code embedding
    if opts.get("qr_svg"):
        svg += _render_embedded_qr(layout, opts, font_family)

    svg += "</svg>"
    return svg


def _render_warped_text(layout: dict, opts: dict, font_family: str) -> str:
    svg = ""
    t = layout["template"]
    half_a = t["sector_angle"] / 2

    if opts.get("logo_data_url"):
        mid_r = (t["inner_r"] + t["outer_r"]) / 2
        edge_angle = -half_a + 0.015
        cx = mid_r * math.sin(edge_angle)
        cy = -mid_r * math.cos(edge_angle)
        slant_len = t["outer_r"] - t["inner_r"]
        img_h = slant_len * 0.5
        img_w = img_h * 0.35
        edge_deg = edge_angle * 180 / math.pi
        svg += (
            f'<image href="{_esc_xml(opts["logo_data_url"])}" '
            f'x="{_ff(cx - img_w / 2)}" y="{_ff(cy - img_h / 2)}" '
            f'width="{_ff(img_w)}" height="{_ff(img_h)}" '
            f'transform="rotate({_ff(edge_deg)}, {_ff(cx)}, {_ff(cy)})" '
            f'preserveAspectRatio="xMidYMid meet"/>'
        )
    elif opts.get("course_name"):
        svg += (
            f'<text fill="white" font-size="7" font-weight="700" '
            f'font-family="{font_family}" opacity="1" text-anchor="middle">'
            f'<textPath href="#textArc1" startOffset="50%">'
            f'{_esc_xml(opts["course_name"])}</textPath></text>'
        )

    if opts.get("hole_range"):
        svg += (
            f'<text fill="white" font-size="4" font-family="{font_family}" '
            f'opacity="1" text-anchor="middle">'
            f'<textPath href="#textArc2" startOffset="50%">'
            f'{_esc_xml(opts["hole_range"])}</textPath></text>'
        )

    if opts.get("hole_yardages"):
        svg += (
            f'<text fill="white" font-size="3" font-family="{font_family}" '
            f'opacity="1" text-anchor="middle">'
            f'<textPath href="#textArc3" startOffset="50%">'
            f'{_esc_xml("  ".join(str(y) for y in opts["hole_yardages"]))}</textPath></text>'
        )

    return svg


def _render_rect_text(layout: dict, opts: dict, font_family: str) -> str:
    svg = ""
    y_mid = layout.get("canvas_height", 700) / 2

    if opts.get("logo_data_url"):
        img_w = 20
        img_h = layout.get("canvas_height", 700) * 0.45
        svg += (
            f'<image href="{_esc_xml(opts["logo_data_url"])}" '
            f'x="3" y="{_ff(y_mid - img_h / 2)}" width="{_ff(img_w)}" height="{_ff(img_h)}" '
            f'transform="rotate(-90, {_ff(3 + img_w / 2)}, {_ff(y_mid)})" '
            f'preserveAspectRatio="xMidYMid meet"/>'
        )
    elif opts.get("course_name"):
        svg += (
            f'<text transform="translate(10, {_ff(y_mid)}) rotate(-90)" '
            f'text-anchor="middle" fill="white" font-size="12" font-weight="700" '
            f'font-family="{font_family}" opacity="1">'
            f'{_esc_xml(opts["course_name"])}</text>'
        )

    if opts.get("hole_range"):
        svg += (
            f'<text transform="translate(22, {_ff(y_mid)}) rotate(-90)" '
            f'text-anchor="middle" fill="white" font-size="7" '
            f'font-family="{font_family}" opacity="1">'
            f'{_esc_xml(opts["hole_range"])}</text>'
        )

    if opts.get("hole_yardages"):
        svg += (
            f'<text transform="translate(31, {_ff(y_mid)}) rotate(-90)" '
            f'text-anchor="middle" fill="white" font-size="5" '
            f'font-family="{font_family}" opacity="1">'
            f'{_esc_xml("  ".join(str(y) for y in opts["hole_yardages"]))}</text>'
        )

    return svg


def _render_onenine_logo(x: float, y: float, height: float) -> str:
    """Render the One Nine logo as inline SVG paths at the given position and height.

    Includes both lines: 'onenine' and 'game.com' with dot separator.
    Original viewBox: 0 0 183 70
    """
    scale = height / 70
    width = 183 * scale
    svg = f'<g transform="translate({_ff(x)}, {_ff(y)}) scale({_ff(scale)})">'
    # --- Line 1: "one" in white ---
    svg += '<path d="M24.791 23.557C24.791 25.628 24.502 27.47 23.923 29.084C23.375 30.697 22.568 32.068 21.503 33.194C20.467 34.29 19.204 35.128 17.712 35.706C16.22 36.254 14.53 36.528 12.642 36.528C10.906 36.528 9.293 36.254 7.801 35.706C6.339 35.128 5.076 34.29 4.01 33.194C2.944 32.068 2.107 30.697 1.498 29.084C0.919 27.47 0.63 25.628 0.63 23.557C0.63 20.786 1.117 18.457 2.092 16.569C3.066 14.651 4.467 13.189 6.293 12.185C8.12 11.18 10.282 10.677 12.779 10.677C15.124 10.677 17.194 11.18 18.991 12.185C20.787 13.189 22.203 14.651 23.238 16.569C24.273 18.457 24.791 20.786 24.791 23.557ZM7.572 23.557C7.572 25.201 7.74 26.587 8.075 27.713C8.44 28.81 9.003 29.647 9.765 30.225C10.526 30.773 11.515 31.048 12.733 31.048C13.951 31.048 14.926 30.773 15.656 30.225C16.418 29.647 16.966 28.81 17.301 27.713C17.666 26.587 17.849 25.201 17.849 23.557C17.849 21.913 17.666 20.543 17.301 19.447C16.966 18.35 16.418 17.528 15.656 16.98C14.895 16.432 13.906 16.158 12.688 16.158C10.891 16.158 9.582 16.782 8.76 18.031C7.968 19.249 7.572 21.091 7.572 23.557Z" fill="white"/>'
    svg += '<path d="M44.574 10.677C47.253 10.677 49.4 11.408 51.014 12.87C52.628 14.301 53.435 16.615 53.435 19.812V36.072H46.629V21.502C46.629 19.705 46.31 18.366 45.67 17.483C45.031 16.569 44.011 16.112 42.61 16.112C40.539 16.112 39.124 16.828 38.362 18.259C37.601 19.66 37.221 21.685 37.221 24.334V36.072H30.415V11.134H35.622L36.535 14.331H36.901C37.449 13.479 38.119 12.794 38.91 12.276C39.702 11.728 40.585 11.332 41.56 11.088C42.534 10.814 43.539 10.677 44.574 10.677Z" fill="white"/>'
    svg += '<path d="M70.709 10.677C73.023 10.677 75.003 11.119 76.647 12.002C78.321 12.885 79.615 14.164 80.529 15.838C81.442 17.513 81.899 19.568 81.899 22.004V25.293H65.822C65.883 27.211 66.446 28.718 67.512 29.814C68.608 30.91 70.115 31.459 72.034 31.459C73.648 31.459 75.109 31.306 76.418 31.002C77.728 30.667 79.083 30.165 80.483 29.495V34.747C79.265 35.356 77.971 35.798 76.601 36.072C75.261 36.376 73.632 36.528 71.714 36.528C69.217 36.528 67.01 36.072 65.091 35.158C63.173 34.214 61.666 32.798 60.57 30.91C59.474 29.023 58.926 26.648 58.926 23.786C58.926 20.862 59.413 18.442 60.387 16.523C61.392 14.575 62.777 13.113 64.543 12.139C66.309 11.165 68.365 10.677 70.709 10.677ZM70.755 15.519C69.446 15.519 68.349 15.945 67.466 16.798C66.614 17.65 66.111 18.975 65.959 20.771H75.505C75.505 19.766 75.322 18.868 74.957 18.076C74.622 17.285 74.104 16.661 73.404 16.204C72.704 15.747 71.821 15.519 70.755 15.519Z" fill="white"/>'
    # --- Line 1: "nine" in red ---
    svg += '<path d="M101.576 10.677C104.255 10.677 106.402 11.408 108.016 12.87C109.63 14.301 110.437 16.615 110.437 19.812V36.072H103.631V21.502C103.631 19.705 103.312 18.366 102.672 17.483C102.033 16.569 101.013 16.112 99.612 16.112C97.541 16.112 96.126 16.828 95.364 18.259C94.603 19.66 94.223 21.685 94.223 24.334V36.072H87.417V11.134H92.624L93.538 14.331H93.903C94.451 13.479 95.121 12.794 95.913 12.276C96.704 11.728 97.587 11.332 98.562 11.088C99.536 10.814 100.541 10.677 101.576 10.677Z" fill="#AC2525"/>'
    svg += '<path d="M124.24 11.134V36.072H117.435V11.134H124.24Z" fill="#AC2525"/>'
    svg += '<path d="M123.464 2.091C122.733 1.604 121.865 1.36 120.86 1.36C119.825 1.36 118.942 1.604 118.211 2.091C117.511 2.548 117.161 3.415 117.161 4.694C117.161 5.943 117.511 6.81 118.211 7.297C118.942 7.785 119.825 8.028 120.86 8.028C121.865 8.028 122.733 7.785 123.464 7.297C124.194 6.81 124.56 5.943 124.56 4.694C124.56 3.415 124.194 2.548 123.464 2.091Z" fill="#AC2525"/>'
    svg += '<path d="M145.509 10.677C148.189 10.677 150.336 11.408 151.949 12.87C153.563 14.301 154.37 16.615 154.37 19.812V36.072H147.565V21.502C147.565 19.705 147.245 18.366 146.606 17.483C145.966 16.569 144.946 16.112 143.546 16.112C141.475 16.112 140.059 16.828 139.298 18.259C138.537 19.66 138.156 21.685 138.156 24.334V36.072H131.351V11.134H136.558L137.471 14.331H137.836C138.385 13.479 139.054 12.794 139.846 12.276C140.638 11.728 141.521 11.332 142.495 11.088C143.469 10.814 144.474 10.677 145.509 10.677Z" fill="#AC2525"/>'
    svg += '<path d="M171.645 10.677C173.959 10.677 175.938 11.119 177.582 12.002C179.257 12.885 180.551 14.164 181.465 15.838C182.378 17.513 182.835 19.568 182.835 22.004V25.293H166.758C166.819 27.211 167.382 28.718 168.448 29.814C169.544 30.91 171.051 31.459 172.969 31.459C174.583 31.459 176.045 31.306 177.354 31.002C178.663 30.667 180.018 30.165 181.419 29.495V34.747C180.201 35.356 178.907 35.798 177.537 36.072C176.197 36.376 174.568 36.528 172.65 36.528C170.153 36.528 167.945 36.072 166.027 35.158C164.109 34.214 162.602 32.798 161.505 30.91C160.409 29.023 159.861 26.648 159.861 23.786C159.861 20.862 160.348 18.442 161.323 16.523C162.328 14.575 163.713 13.113 165.479 12.139C167.245 11.165 169.3 10.677 171.645 10.677ZM171.69 15.519C170.381 15.519 169.285 15.945 168.402 16.798C167.549 17.65 167.047 18.975 166.895 20.771H176.44C176.44 19.766 176.258 18.868 175.892 18.076C175.557 17.285 175.04 16.661 174.34 16.204C173.639 15.747 172.756 15.519 171.69 15.519Z" fill="#AC2525"/>'
    # --- Line 2: "game.com" in white ---
    svg += '<path d="M17.333 44.358C18.486 44.358 19.519 44.575 20.433 45.01C21.368 45.445 22.162 46.109 22.814 47H22.977L23.369 44.684H25.652V62.464C25.652 64.117 25.37 65.498 24.804 66.607C24.239 67.738 23.38 68.586 22.227 69.152C21.074 69.717 19.606 70 17.823 70C16.561 70 15.398 69.902 14.332 69.706C13.288 69.532 12.353 69.261 11.526 68.891V66.248C12.092 66.531 12.712 66.77 13.386 66.966C14.06 67.184 14.789 67.347 15.572 67.455C16.355 67.564 17.159 67.619 17.986 67.619C19.486 67.619 20.661 67.173 21.509 66.281C22.379 65.411 22.814 64.215 22.814 62.692V62.007C22.814 61.746 22.825 61.377 22.847 60.898C22.868 60.398 22.89 60.05 22.912 59.854H22.781C22.173 60.746 21.411 61.409 20.498 61.844C19.606 62.279 18.562 62.497 17.366 62.497C15.104 62.497 13.332 61.703 12.048 60.115C10.787 58.527 10.156 56.309 10.156 53.46C10.156 51.589 10.439 49.98 11.004 48.632C11.592 47.261 12.418 46.207 13.484 45.467C14.549 44.728 15.833 44.358 17.333 44.358ZM17.725 46.772C16.746 46.772 15.909 47.033 15.213 47.555C14.539 48.077 14.017 48.838 13.647 49.839C13.299 50.839 13.125 52.057 13.125 53.493C13.125 55.646 13.516 57.299 14.299 58.451C15.104 59.582 16.268 60.148 17.79 60.148C18.682 60.148 19.443 60.039 20.074 59.821C20.704 59.582 21.226 59.223 21.64 58.745C22.053 58.245 22.357 57.614 22.553 56.853C22.749 56.092 22.847 55.189 22.847 54.145V53.46C22.847 51.872 22.662 50.589 22.292 49.61C21.944 48.632 21.39 47.914 20.628 47.457C19.867 47 18.899 46.772 17.725 46.772Z" fill="white"/>'
    svg += '<path d="M37.829 44.391C39.96 44.391 41.537 44.858 42.559 45.793C43.581 46.729 44.092 48.218 44.092 50.263V62.17H42.004L41.45 59.691H41.319C40.819 60.322 40.297 60.855 39.753 61.29C39.231 61.703 38.622 62.007 37.926 62.203C37.252 62.399 36.426 62.497 35.447 62.497C34.403 62.497 33.457 62.312 32.609 61.942C31.782 61.572 31.13 61.007 30.651 60.246C30.173 59.463 29.934 58.484 29.934 57.31C29.934 55.57 30.619 54.232 31.989 53.297C33.359 52.34 35.469 51.818 38.318 51.731L41.287 51.633V50.589C41.287 49.132 40.971 48.121 40.341 47.555C39.71 46.99 38.818 46.707 37.665 46.707C36.752 46.707 35.882 46.848 35.056 47.131C34.229 47.392 33.457 47.696 32.739 48.044L31.858 45.891C32.62 45.478 33.522 45.13 34.566 44.847C35.61 44.543 36.698 44.391 37.829 44.391ZM38.677 53.721C36.502 53.808 34.99 54.156 34.142 54.765C33.316 55.374 32.902 56.233 32.902 57.342C32.902 58.321 33.196 59.039 33.783 59.495C34.392 59.952 35.164 60.18 36.1 60.18C37.578 60.18 38.807 59.778 39.786 58.973C40.765 58.147 41.254 56.885 41.254 55.189V53.623L38.677 53.721Z" fill="white"/>'
    svg += '<path d="M68.676 44.358C70.655 44.358 72.134 44.869 73.113 45.891C74.091 46.892 74.581 48.523 74.581 50.785V62.17H71.742V50.915C71.742 49.545 71.449 48.512 70.862 47.816C70.296 47.12 69.404 46.772 68.186 46.772C66.49 46.772 65.272 47.261 64.533 48.24C63.815 49.219 63.456 50.643 63.456 52.514V62.17H60.618V50.915C60.618 50.002 60.487 49.241 60.226 48.632C59.965 48.001 59.574 47.533 59.052 47.229C58.53 46.924 57.856 46.772 57.029 46.772C55.855 46.772 54.93 47.022 54.256 47.522C53.582 48.001 53.093 48.708 52.788 49.643C52.505 50.578 52.364 51.731 52.364 53.101V62.17H49.493V44.684H51.809L52.233 47.066H52.397C52.766 46.457 53.212 45.956 53.734 45.565C54.278 45.152 54.876 44.847 55.528 44.652C56.181 44.456 56.855 44.358 57.551 44.358C58.9 44.358 60.02 44.597 60.911 45.076C61.825 45.554 62.488 46.294 62.901 47.294H63.064C63.652 46.294 64.446 45.554 65.446 45.076C66.468 44.597 67.545 44.358 68.676 44.358Z" fill="white"/>'
    svg += '<path d="M86.735 44.358C88.236 44.358 89.519 44.684 90.585 45.337C91.672 45.989 92.499 46.913 93.064 48.11C93.651 49.284 93.945 50.665 93.945 52.253V53.982H81.972C82.016 55.961 82.516 57.473 83.473 58.517C84.452 59.539 85.811 60.05 87.551 60.05C88.66 60.05 89.639 59.952 90.487 59.756C91.357 59.539 92.249 59.234 93.162 58.843V61.355C92.27 61.746 91.389 62.029 90.52 62.203C89.65 62.399 88.616 62.497 87.42 62.497C85.767 62.497 84.299 62.16 83.016 61.485C81.755 60.811 80.765 59.811 80.047 58.484C79.351 57.135 79.003 55.493 79.003 53.558C79.003 51.644 79.319 50.002 79.949 48.632C80.602 47.261 81.505 46.207 82.657 45.467C83.832 44.728 85.191 44.358 86.735 44.358ZM86.703 46.707C85.332 46.707 84.245 47.153 83.44 48.044C82.657 48.914 82.19 50.132 82.037 51.698H90.944C90.944 50.698 90.791 49.828 90.487 49.088C90.182 48.349 89.715 47.773 89.084 47.359C88.475 46.924 87.681 46.707 86.703 46.707Z" fill="white"/>'
    # --- Dot separator ---
    svg += '<circle cx="100" cy="60" r="2" fill="#D9D9D9"/>'
    # --- "com" in white ---
    svg += '<path d="M112.26 62.497C110.716 62.497 109.335 62.181 108.117 61.551C106.921 60.92 105.975 59.941 105.279 58.614C104.605 57.288 104.268 55.591 104.268 53.525C104.268 51.372 104.626 49.621 105.344 48.273C106.062 46.924 107.03 45.935 108.248 45.304C109.487 44.673 110.89 44.358 112.456 44.358C113.348 44.358 114.207 44.456 115.033 44.652C115.86 44.826 116.534 45.043 117.056 45.304L116.175 47.686C115.653 47.49 115.044 47.305 114.348 47.131C113.652 46.957 113 46.87 112.391 46.87C111.216 46.87 110.249 47.12 109.487 47.62C108.726 48.121 108.161 48.86 107.791 49.839C107.421 50.817 107.236 52.035 107.236 53.493C107.236 54.884 107.421 56.07 107.791 57.048C108.161 58.027 108.715 58.767 109.455 59.267C110.194 59.767 111.118 60.017 112.228 60.017C113.185 60.017 114.022 59.919 114.74 59.724C115.479 59.528 116.153 59.289 116.762 59.006V61.551C116.175 61.855 115.523 62.083 114.805 62.236C114.109 62.41 113.261 62.497 112.26 62.497Z" fill="white"/>'
    svg += '<path d="M136.123 53.395C136.123 54.852 135.928 56.146 135.536 57.277C135.166 58.386 134.623 59.332 133.905 60.115C133.209 60.898 132.35 61.496 131.328 61.909C130.327 62.301 129.207 62.497 127.968 62.497C126.815 62.497 125.749 62.301 124.77 61.909C123.792 61.496 122.943 60.898 122.226 60.115C121.508 59.332 120.943 58.386 120.529 57.277C120.138 56.146 119.942 54.852 119.942 53.395C119.942 51.459 120.268 49.828 120.921 48.501C121.573 47.153 122.509 46.13 123.726 45.434C124.944 44.717 126.391 44.358 128.065 44.358C129.653 44.358 131.045 44.717 132.241 45.434C133.459 46.13 134.405 47.153 135.079 48.501C135.775 49.828 136.123 51.459 136.123 53.395ZM122.911 53.395C122.911 54.765 123.085 55.961 123.433 56.983C123.803 57.984 124.368 58.756 125.129 59.3C125.89 59.843 126.858 60.115 128.033 60.115C129.207 60.115 130.175 59.843 130.936 59.3C131.697 58.756 132.252 57.984 132.6 56.983C132.97 55.961 133.155 54.765 133.155 53.395C133.155 52.003 132.97 50.817 132.6 49.839C132.23 48.86 131.665 48.11 130.904 47.588C130.164 47.044 129.196 46.772 128 46.772C126.217 46.772 124.923 47.359 124.118 48.534C123.313 49.708 122.911 51.328 122.911 53.395Z" fill="white"/>'
    svg += '<path d="M159.856 44.358C161.835 44.358 163.314 44.869 164.293 45.891C165.272 46.892 165.761 48.523 165.761 50.785V62.17H162.923V50.915C162.923 49.545 162.629 48.512 162.042 47.816C161.476 47.12 160.585 46.772 159.367 46.772C157.67 46.772 156.452 47.261 155.713 48.24C154.995 49.219 154.636 50.643 154.636 52.514V62.17H151.798V50.915C151.798 50.002 151.668 49.241 151.407 48.632C151.146 48.001 150.754 47.533 150.232 47.229C149.71 46.924 149.036 46.772 148.209 46.772C147.035 46.772 146.111 47.022 145.436 47.522C144.762 48.001 144.273 48.708 143.968 49.643C143.686 50.578 143.544 51.731 143.544 53.101V62.17H140.673V44.684H142.99L143.414 47.066H143.577C143.947 46.457 144.393 45.956 144.914 45.565C145.458 45.152 146.056 44.847 146.709 44.652C147.361 44.456 148.035 44.358 148.731 44.358C150.08 44.358 151.2 44.597 152.092 45.076C153.005 45.554 153.668 46.294 154.082 47.294H154.245C154.832 46.294 155.626 45.554 156.626 45.076C157.649 44.597 158.725 44.358 159.856 44.358Z" fill="white"/>'
    svg += '</g>'
    return svg, width


def _render_embedded_qr(layout: dict, opts: dict, font_family: str = "'Arial', sans-serif") -> str:
    """Embed a QR code with 'Scan for your scorecard' text and logo."""
    qr_svg = opts.get("qr_svg", "")
    if not qr_svg:
        return ""

    # Extract QR path data and viewBox from the generated SVG
    path_match = re.search(r'd="([^"]+)"', qr_svg)
    vb_match = re.search(r'viewBox="([^"]+)"', qr_svg)
    if not path_match:
        return ""

    qr_path_d = path_match.group(1)
    # Parse viewBox to get QR native size
    qr_native = 33  # default
    if vb_match:
        parts = vb_match.group(1).split()
        if len(parts) == 4:
            qr_native = float(parts[2])

    is_warped = layout.get("warped") and layout.get("template")

    if is_warped:
        t = layout["template"]
        half_a = t["sector_angle"] / 2
        slant = t["outer_r"] - t["inner_r"]
        qr_size = slant * 0.12

        # Position at bottom-LEFT of glass sector (negative angle)
        edge_angle = -(half_a - 0.08)
        r = t["inner_r"] + slant * 0.15
        cx = r * math.sin(edge_angle)
        cy = -r * math.cos(edge_angle)
        rot_deg = edge_angle * 180 / math.pi

        scale = qr_size / qr_native
        logo_h = qr_size * 0.7
        logo_w = logo_h * (183 / 71)  # aspect ratio of onenine.png
        text_fs = qr_size * 0.12

        svg = f'<g transform="rotate({_ff(rot_deg)}, {_ff(cx)}, {_ff(cy)})">'
        # QR code path — white on transparent
        svg += (
            f'<g transform="translate({_ff(cx - qr_size / 2)}, {_ff(cy - qr_size / 2)}) '
            f'scale({_ff(scale)})">'
            f'<path d="{qr_path_d}" fill="#ffffff"/>'
            f'</g>'
        )
        # "Scan for your scorecard" text below QR
        svg += (
            f'<text x="{_ff(cx)}" y="{_ff(cy + qr_size / 2 + text_fs + 0.5)}" '
            f'text-anchor="middle" dominant-baseline="hanging" '
            f'fill="#ffffff" font-size="{_ff(text_fs)}" '
            f'font-family="{font_family}" opacity="0.85">Scan for your scorecard</text>'
        )
        # Logo to the right of QR (toward center of glass)
        logo_x = cx + qr_size / 2 + 2
        logo_y = cy - logo_h / 2
        logo_svg, _ = _render_onenine_logo(logo_x, logo_y, logo_h)
        svg += logo_svg
        svg += '</g>'
        return svg
    else:
        cw = layout.get("canvas_width", 900)
        ch = layout.get("canvas_height", 700)
        qr_size = 40
        cx = cw - 60
        cy = ch - 60
        scale = qr_size / qr_native
        logo_h = qr_size * 0.6
        logo_w = logo_h * (183 / 71)
        text_fs = 4

        svg = '<g>'
        # QR code — white on transparent
        svg += (
            f'<g transform="translate({_ff(cx - qr_size / 2)}, {_ff(cy - qr_size / 2)}) '
            f'scale({_ff(scale)})">'
            f'<path d="{qr_path_d}" fill="#ffffff"/>'
            f'</g>'
        )
        # Text below
        svg += (
            f'<text x="{_ff(cx)}" y="{_ff(cy + qr_size / 2 + 5)}" '
            f'text-anchor="middle" fill="#ffffff" font-size="{text_fs}" '
            f'font-family="{font_family}" opacity="0.85">Scan for your scorecard</text>'
        )
        # Logo to right
        logo_x = cx + qr_size / 2 + 5
        logo_y = cy - logo_h / 2
        logo_svg, _ = _render_onenine_logo(logo_x, logo_y, logo_h)
        svg += logo_svg
        svg += '</g>'
        return svg
