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
    _consolidate = opts.get("consolidate_layers", False)
    _white = layer in ("all", "white")
    _green = layer in ("all", "green")
    _blue = layer in ("all", "blue") or (layer == "white" and _consolidate)
    _tan = layer in ("all", "tan") or (layer == "white" and _consolidate)

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
    hidden = opts.get("hidden_layers", [])
    _bg_opacity = opts.get("background_opacity")  # None = fully opaque
    _show_bg = _all and "background" not in hidden
    if is_warped:
        from app.services.render.glass_template import glass_wrap_path
        svg += '<g clip-path="url(#glassClip)">'
        if _show_bg:
            opacity_attr = f' opacity="{_bg_opacity}"' if _bg_opacity is not None else ''
            svg += f'<path d="{glass_wrap_path(layout["template"])}" fill="{_BG_COLOR}"{opacity_attr}/>'
    else:
        if _show_bg:
            opacity_attr = f' opacity="{_bg_opacity}"' if _bg_opacity is not None else ''
            svg += (
                f'<rect x="0" y="0" width="{layout.get("canvas_width", 900)}" '
                f'height="{layout.get("canvas_height", 700)}" fill="{_BG_COLOR}"{opacity_attr} rx="4"/>'
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

        # QR code + white parts of logo
        if opts.get("qr_svg"):
            svg += _render_embedded_qr(layout, opts, font_family, logo_layer="white")

    if _green:
        # Green parts of logo (lettering) next to QR
        if opts.get("qr_svg"):
            svg += _render_embedded_qr(layout, opts, font_family, logo_layer="green", qr_only=False)

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


def _render_splitthetee_logo(x: float, y: float, height: float, layer: str = "all") -> str:
    """Render the Split the Tee logo as inline SVG paths at the given position and height.

    Original viewBox: 0 0 2068 542. Actual content bbox: x 4..2055, y 141..376.
    We translate to origin then scale to requested height.

    layer="all"   → full logo (tee pin white + green lettering)
    layer="white" → only the white tee pin
    layer="green" → only the green lettering
    """
    # Actual content bounding box
    cx, cy, cw, ch = 4, 141, 2051, 235
    scale = height / ch
    width = cw * scale
    _white = layer in ("all", "white")
    _green = layer in ("all", "green")

    svg = (
        f'<g transform="translate({_ff(x)}, {_ff(y)}) scale({scale:.6f}) '
        f'translate({_ff(-cx)}, {_ff(-cy)})">'
    )
    # Tee pin icon (white)
    if _white:
        svg += '<path d="M1081.47 203.749L1071 202.211V144.076L1081.47 141C1081.47 141 1089.47 151.151 1108.86 156.995C1128.26 162.839 1142.11 161.916 1142.11 161.916L1150.11 181.295L1146.11 202.211L1154.12 216.975L1150.11 235.123L1154.12 273.88L1155.96 235.123L1163.04 216.975L1157.5 199.442L1166.12 181.295L1164.89 161.916C1164.89 161.916 1178.74 162.839 1198.14 156.995C1217.53 151.151 1225.53 141 1225.53 141L1236 144.076V202.211L1225.53 203.749C1225.53 203.749 1207.99 187.139 1190.75 187.754C1173.51 188.369 1170.74 210.823 1170.74 210.823V332.322C1170.74 336.013 1156.27 376 1153.5 376C1150.73 376 1136.26 336.013 1136.26 332.322V210.823C1136.26 210.823 1133.49 188.369 1116.25 187.754C1099.01 187.139 1081.47 203.749 1081.47 203.749Z" fill="white" stroke="white"/>'
    if _green:
        svg += _splitthetee_green_paths()
    svg += '</g>'
    return svg, width


def _splitthetee_green_paths() -> str:
    """Return the green lettering paths for the Split the Tee logo."""
    svg = ''
    # S
    svg += '<path d="M62.8418 368.93C52.1973 368.93 42.3828 366.195 33.3984 360.727C24.5117 355.258 17.3828 347.982 12.0117 338.9C6.73828 329.721 4.10156 319.662 4.10156 308.725V294.955C4.10156 293.881 4.58984 293.344 5.56641 293.344H39.2578C40.0391 293.344 40.4297 293.881 40.4297 294.955V308.725C40.4297 315.268 42.627 320.932 47.0215 325.717C51.416 330.404 56.6895 332.748 62.8418 332.748C69.0918 332.748 74.4141 330.355 78.8086 325.57C83.2031 320.688 85.4004 315.072 85.4004 308.725C85.4004 301.4 80.6152 295.004 71.0449 289.535C69.4824 288.559 67.4316 287.387 64.8926 286.02C62.4512 284.555 59.5215 282.895 56.1035 281.039C52.6855 279.184 49.3652 277.377 46.1426 275.619C42.9199 273.764 39.7949 272.006 36.7676 270.346C25.8301 263.9 17.6758 255.844 12.3047 246.176C7.03125 236.41 4.39453 225.473 4.39453 213.363C4.39453 202.23 7.12891 192.172 12.5977 183.188C18.0664 174.301 25.1953 167.27 33.9844 162.094C42.8711 156.82 52.4902 154.184 62.8418 154.184C73.4863 154.184 83.252 156.82 92.1387 162.094C101.025 167.465 108.105 174.594 113.379 183.48C118.75 192.367 121.436 202.328 121.436 213.363V237.973C121.436 238.754 121.045 239.145 120.264 239.145H86.5723C85.791 239.145 85.4004 238.754 85.4004 237.973L85.1074 213.363C85.1074 206.332 82.9102 200.619 78.5156 196.225C74.1211 191.83 68.8965 189.633 62.8418 189.633C56.6895 189.633 51.416 191.977 47.0215 196.664C42.627 201.352 40.4297 206.918 40.4297 213.363C40.4297 219.906 41.7969 225.375 44.5312 229.77C47.3633 234.164 52.4902 238.363 59.9121 242.367C60.6934 242.758 62.5 243.734 65.332 245.297C68.1641 246.859 71.2891 248.617 74.707 250.57C78.2227 252.426 81.3965 254.135 84.2285 255.697C87.0605 257.162 88.7695 258.041 89.3555 258.334C99.3164 263.9 107.178 270.736 112.939 278.842C118.799 286.947 121.729 296.908 121.729 308.725C121.729 320.15 119.092 330.404 113.818 339.486C108.447 348.568 101.318 355.746 92.4316 361.02C83.5449 366.293 73.6816 368.93 62.8418 368.93Z" fill="#519E41"/>'
    # P
    svg += '<path d="M192.686 366H158.994C158.018 366 157.529 365.512 157.529 364.535L158.115 158.432C158.115 157.65 158.506 157.26 159.287 157.26H217.002C235.361 157.26 249.863 162.875 260.508 174.105C271.25 185.238 276.621 200.424 276.621 219.662C276.621 233.725 273.838 245.98 268.271 256.43C262.607 266.781 255.283 274.789 246.299 280.453C237.314 286.117 227.549 288.949 217.002 288.949H194.15V364.535C194.15 365.512 193.662 366 192.686 366ZM217.002 192.855L194.15 193.148V252.621H217.002C223.35 252.621 228.867 249.594 233.555 243.539C238.242 237.387 240.586 229.428 240.586 219.662C240.586 211.85 238.486 205.453 234.287 200.473C230.088 195.395 224.326 192.855 217.002 192.855Z" fill="#519E41"/>'
    # L
    svg += '<path d="M410.127 366H313.154C312.373 366 311.982 365.512 311.982 364.535L312.275 158.725C312.275 157.748 312.764 157.26 313.74 157.26H347.139C348.115 157.26 348.604 157.748 348.604 158.725L348.311 329.086H410.127C411.104 329.086 411.592 329.574 411.592 330.551V364.535C411.592 365.512 411.104 366 410.127 366Z" fill="#519E41"/>'
    # I
    svg += '<path d="M481.67 366H447.686C446.709 366 446.221 365.512 446.221 364.535L446.514 158.432C446.514 157.65 446.904 157.26 447.686 157.26H481.377C482.158 157.26 482.549 157.65 482.549 158.432L482.842 364.535C482.842 365.512 482.451 366 481.67 366Z" fill="#519E41"/>'
    # T
    svg += '<path d="M588.223 366H554.385C553.506 366 553.066 365.512 553.066 364.535V193.441H514.102C513.125 193.441 512.637 192.953 512.637 191.977L512.93 158.432C512.93 157.65 513.32 157.26 514.102 157.26H628.066C629.141 157.26 629.678 157.65 629.678 158.432V191.977C629.678 192.953 629.287 193.441 628.506 193.441H589.102L589.395 364.535C589.395 365.512 589.004 366 588.223 366Z" fill="#519E41"/>'
    # T
    svg += '<path d="M723.34 366H689.502C688.623 366 688.184 365.512 688.184 364.535V193.441H649.219C648.242 193.441 647.754 192.953 647.754 191.977L648.047 158.432C648.047 157.65 648.438 157.26 649.219 157.26H763.184C764.258 157.26 764.795 157.65 764.795 158.432V191.977C764.795 192.953 764.404 193.441 763.623 193.441H724.219L724.512 364.535C724.512 365.512 724.121 366 723.34 366Z" fill="#519E41"/>'
    # H
    svg += '<path d="M829.6 366H795.615C794.834 366 794.443 365.512 794.443 364.535L794.736 158.432C794.736 157.65 795.225 157.26 796.201 157.26H829.6C830.576 157.26 831.064 157.65 831.064 158.432L830.771 240.023H875.742V158.432C875.742 157.65 876.133 157.26 876.914 157.26H910.312C911.289 157.26 911.777 157.65 911.777 158.432L912.363 364.535C912.363 365.512 911.875 366 910.898 366H877.207C876.23 366 875.742 365.512 875.742 364.535V276.352H830.771V364.535C830.771 365.512 830.381 366 829.6 366Z" fill="#519E41"/>'
    # E
    svg += '<path d="M1049.97 366H952.998C952.217 366 951.826 365.512 951.826 364.535L952.119 158.432C952.119 157.65 952.51 157.26 953.291 157.26H1049.68C1050.46 157.26 1050.85 157.748 1050.85 158.725V192.27C1050.85 193.051 1050.46 193.441 1049.68 193.441H988.154V240.316H1049.68C1050.46 240.316 1050.85 240.707 1050.85 241.488L1051.14 275.473C1051.14 276.254 1050.75 276.645 1049.97 276.645H988.154V329.086H1049.97C1050.75 329.086 1051.14 329.574 1051.14 330.551V364.828C1051.14 365.609 1050.75 366 1049.97 366Z" fill="#519E41"/>'
    # E
    svg += '<path d="M1355.88 366H1258.9C1258.12 366 1257.73 365.512 1257.73 364.535L1258.03 158.432C1258.03 157.65 1258.42 157.26 1259.2 157.26H1355.58C1356.37 157.26 1356.76 157.748 1356.76 158.725V192.27C1356.76 193.051 1356.37 193.441 1355.58 193.441H1294.06V240.316H1355.58C1356.37 240.316 1356.76 240.707 1356.76 241.488L1357.05 275.473C1357.05 276.254 1356.66 276.645 1355.88 276.645H1294.06V329.086H1355.88C1356.66 329.086 1357.05 329.574 1357.05 330.551V364.828C1357.05 365.609 1356.66 366 1355.88 366Z" fill="#519E41"/>'
    # E
    svg += '<path d="M1496.85 366H1399.88C1399.1 366 1398.71 365.512 1398.71 364.535L1399 158.432C1399 157.65 1399.39 157.26 1400.17 157.26H1496.56C1497.34 157.26 1497.73 157.748 1497.73 158.725V192.27C1497.73 193.051 1497.34 193.441 1496.56 193.441H1435.04V240.316H1496.56C1497.34 240.316 1497.73 240.707 1497.73 241.488L1498.03 275.473C1498.03 276.254 1497.63 276.645 1496.85 276.645H1435.04V329.086H1496.85C1497.63 329.086 1498.03 329.574 1498.03 330.551V364.828C1498.03 365.609 1497.63 366 1496.85 366Z" fill="#519E41"/>'
    # Dot
    svg += '<path d="M1574.84 366H1540.86C1540.08 366 1539.69 365.609 1539.69 364.828V330.844C1539.69 330.062 1540.08 329.672 1540.86 329.672H1574.84C1575.62 329.672 1576.01 330.062 1576.01 330.844V364.828C1576.01 365.609 1575.62 366 1574.84 366Z" fill="#519E41"/>'
    # C
    svg += '<path d="M1670.85 368.93C1660.01 368.93 1650.1 366.195 1641.11 360.727C1632.22 355.258 1625.14 347.934 1619.87 338.754C1614.7 329.477 1612.11 319.174 1612.11 307.846L1612.4 214.242C1612.4 203.109 1614.94 193.051 1620.02 184.066C1625.1 174.984 1632.08 167.709 1640.96 162.24C1649.95 156.674 1659.91 153.891 1670.85 153.891C1681.98 153.891 1691.89 156.576 1700.58 161.947C1709.37 167.318 1716.36 174.594 1721.53 183.773C1726.8 192.855 1729.44 203.012 1729.44 214.242V228.012C1729.44 228.793 1729.05 229.184 1728.27 229.184H1694.58C1693.8 229.184 1693.41 228.793 1693.41 228.012V214.242C1693.41 207.602 1691.26 201.889 1686.96 197.104C1682.66 192.318 1677.29 189.926 1670.85 189.926C1663.72 189.926 1658.25 192.367 1654.44 197.25C1650.63 202.133 1648.73 207.797 1648.73 214.242V307.846C1648.73 315.17 1650.88 321.176 1655.17 325.863C1659.47 330.453 1664.7 332.748 1670.85 332.748C1677.29 332.748 1682.66 330.209 1686.96 325.131C1691.26 319.955 1693.41 314.193 1693.41 307.846V293.93C1693.41 293.148 1693.8 292.758 1694.58 292.758H1728.56C1729.34 292.758 1729.73 293.148 1729.73 293.93V307.846C1729.73 319.076 1727.1 329.33 1721.82 338.607C1716.45 347.787 1709.37 355.16 1700.58 360.727C1691.79 366.195 1681.88 368.93 1670.85 368.93Z" fill="#519E41"/>'
    # O
    svg += '<path d="M1822.08 368.93C1811.43 368.93 1801.62 366.195 1792.63 360.727C1783.75 355.258 1776.57 347.982 1771.1 338.9C1765.73 329.721 1763.04 319.662 1763.04 308.725L1763.34 213.656C1763.34 202.523 1766.02 192.514 1771.39 183.627C1776.67 174.643 1783.8 167.465 1792.78 162.094C1801.77 156.625 1811.53 153.891 1822.08 153.891C1833.02 153.891 1842.83 156.576 1851.52 161.947C1860.31 167.318 1867.34 174.545 1872.62 183.627C1877.99 192.611 1880.67 202.621 1880.67 213.656L1880.96 308.725C1880.96 319.662 1878.33 329.672 1873.05 338.754C1867.68 347.934 1860.55 355.258 1851.67 360.727C1842.78 366.195 1832.92 368.93 1822.08 368.93ZM1822.08 332.748C1828.13 332.748 1833.41 330.307 1837.9 325.424C1842.39 320.443 1844.64 314.877 1844.64 308.725L1844.34 213.656C1844.34 207.016 1842.24 201.4 1838.04 196.811C1833.85 192.221 1828.52 189.926 1822.08 189.926C1815.93 189.926 1810.65 192.172 1806.26 196.664C1801.86 201.156 1799.67 206.82 1799.67 213.656V308.725C1799.67 315.268 1801.86 320.932 1806.26 325.717C1810.65 330.404 1815.93 332.748 1822.08 332.748Z" fill="#519E41"/>'
    # M
    svg += '<path d="M1953.83 366H1919.84C1919.06 366 1918.67 365.512 1918.67 364.535L1919.26 158.432C1919.26 157.65 1919.65 157.26 1920.43 157.26H1957.05C1957.83 157.26 1958.51 157.65 1959.1 158.432L1986.49 197.982L2013.74 158.432C2014.32 157.65 2015.06 157.26 2015.94 157.26H2052.7C2053.58 157.26 2054.02 157.65 2054.02 158.432L2054.61 364.535C2054.61 365.512 2054.22 366 2053.44 366H2019.45C2018.67 366 2018.28 365.512 2018.28 364.535L2017.99 211.459L1986.49 257.162L1955.29 211.459L1955 364.535C1955 365.512 1954.61 366 1953.83 366Z" fill="#519E41"/>'
    return svg


def _render_embedded_qr(layout: dict, opts: dict, font_family: str = "'Arial', sans-serif",
                        logo_layer: str = "all", qr_only: bool = True) -> str:
    """Embed a QR code with 'Scan for your scorecard' text and logo.

    logo_layer controls which parts of the logo are rendered.
    When qr_only=False, only the logo is rendered (no QR code or text) — used
    for rendering the green logo lettering on the green cricut layer.
    """
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
        text_fs = qr_size * 0.12
        # Logo: constrain width to match QR code width, derive height from aspect ratio
        logo_aspect = 2051 / 235  # width / height of splitthetee logo content
        logo_w = qr_size
        logo_h = logo_w / logo_aspect

        svg = f'<g transform="rotate({_ff(rot_deg)}, {_ff(cx)}, {_ff(cy)})">'
        # Logo above QR
        logo_x = cx - logo_w / 2
        logo_y = cy - qr_size / 2 - logo_h - 1.5
        logo_svg, _ = _render_splitthetee_logo(logo_x, logo_y, logo_h, layer=logo_layer)
        svg += logo_svg
        if qr_only is not False:
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
        svg += '</g>'
        return svg
    else:
        cw = layout.get("canvas_width", 900)
        ch = layout.get("canvas_height", 700)
        qr_size = 40
        cx = cw - 60
        cy = ch - 60
        scale = qr_size / qr_native
        text_fs = 4
        # Logo: constrain width to match QR code width
        logo_aspect = 2051 / 235
        logo_w = qr_size
        logo_h = logo_w / logo_aspect

        svg = '<g>'
        # Logo above QR
        logo_x = cx - logo_w / 2
        logo_y = cy - qr_size / 2 - logo_h - 3
        logo_svg, _ = _render_splitthetee_logo(logo_x, logo_y, logo_h, layer=logo_layer)
        svg += logo_svg
        if qr_only is not False:
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
        svg += '</g>'
        return svg
