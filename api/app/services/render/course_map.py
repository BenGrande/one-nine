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

LAYER_ORDER = ["course_boundary", "rough", "water", "fairway", "bunker", "tee", "green", "path"]


def _project(lat: float, lng: float, center_lat: float, center_lng: float) -> tuple[float, float]:
    cos_lat = math.cos(math.radians(center_lat))
    x = (lng - center_lng) * cos_lat * 111320
    y = -(lat - center_lat) * 110540
    return x, y


def _centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def render_course_map_svg(
    features: list[dict],
    center: list[float],
    width: int = 600,
    height: int = 300,
    hole_stats: dict[int | str, dict] | None = None,
) -> str:
    if not features:
        return ""

    hole_stats = hole_stats or {}
    center_lat, center_lng = center[0], center[1]

    # Categories we render or use for labels (hole lines aren't drawn as fills
    # but are needed for positioning stats labels)
    KNOWN_CATS = set(CATEGORY_STYLES.keys()) | {"hole"}

    # Project all coordinates
    projected: list[tuple[str, list[tuple[float, float]], dict]] = []
    all_x, all_y = [], []

    for f in features:
        cat = f.get("category", "")
        coords = f.get("coords", [])
        if not coords or cat not in KNOWN_CATS:
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

    # Bounding box with padding
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    data_w = max_x - min_x or 1
    data_h = max_y - min_y or 1
    pad_frac = 0.05
    min_x -= data_w * pad_frac
    max_x += data_w * pad_frac
    min_y -= data_h * pad_frac
    max_y += data_h * pad_frac
    data_w = max_x - min_x
    data_h = max_y - min_y

    # Scale to fit
    scale = min(width / data_w, height / data_h)
    svg_w = data_w * scale
    svg_h = data_h * scale
    offset_x = (width - svg_w) / 2
    offset_y = (height - svg_h) / 2

    def to_svg(x: float, y: float) -> tuple[float, float]:
        return (x - min_x) * scale + offset_x, (y - min_y) * scale + offset_y

    # Sort by layer order
    order_map = {cat: i for i, cat in enumerate(LAYER_ORDER)}
    projected.sort(key=lambda p: order_map.get(p[0], 99))

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'style="max-width:100%;height:auto;">'
    )
    svg += f'<rect width="{width}" height="{height}" fill="#1a3a1a" rx="8"/>'

    # ── Render terrain features ──
    for cat, pts, feat in projected:
        if cat not in CATEGORY_STYLES:
            continue
        style = CATEGORY_STYLES[cat]
        svg_pts = [to_svg(x, y) for x, y in pts]

        if cat == "path":
            points_str = " ".join(f"{_ff(x)},{_ff(y)}" for x, y in svg_pts)
            svg += (
                f'<polyline points="{points_str}" '
                f'fill="none" stroke="{style["stroke"]}" '
                f'stroke-width="1" opacity="{style["opacity"]}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        elif len(svg_pts) >= 3:
            points_str = " ".join(f"{_ff(x)},{_ff(y)}" for x, y in svg_pts)
            stroke_attr = f'stroke="{style["stroke"]}" stroke-width="0.5"' if style["stroke"] != "none" else 'stroke="none"'
            svg += (
                f'<polygon points="{points_str}" '
                f'fill="{style["fill"]}" {stroke_attr} '
                f'opacity="{style["opacity"]}"/>'
            )

    # ── Hole routing lines ──
    for cat, pts, feat in projected:
        if cat != "hole":
            continue
        if len(pts) >= 2:
            svg_pts = [to_svg(x, y) for x, y in pts]
            points_str = " ".join(f"{_ff(x)},{_ff(y)}" for x, y in svg_pts)
            svg += (
                f'<polyline points="{points_str}" '
                f'fill="none" stroke="rgba(255,255,255,0.2)" '
                f'stroke-width="0.8" stroke-dasharray="2,1.5"/>'
            )

    # ── Build position maps for labeling ──
    # Collect all tee, green, and hole-line positions (keyed by ref if available)
    tee_centroids_by_ref: dict[str, tuple[float, float]] = {}
    green_centroids_by_ref: dict[str, tuple[float, float]] = {}
    hole_line_starts: dict[str, tuple[float, float]] = {}  # tee end of hole line
    hole_line_ends: dict[str, tuple[float, float]] = {}    # green end of hole line

    # Also collect unkeyed tees/greens for proximity matching
    all_tee_centroids: list[tuple[float, float]] = []
    all_green_centroids: list[tuple[float, float]] = []

    for cat, pts, feat in projected:
        svg_pts = [to_svg(x, y) for x, y in pts]
        c = _centroid(svg_pts)
        ref = feat.get("ref")

        if cat == "tee":
            all_tee_centroids.append(c)
            if ref:
                tee_centroids_by_ref[str(ref)] = c
        elif cat == "green":
            all_green_centroids.append(c)
            if ref:
                green_centroids_by_ref[str(ref)] = c
        elif cat == "hole" and len(svg_pts) >= 2:
            if ref:
                hole_line_starts[str(ref)] = svg_pts[0]
                hole_line_ends[str(ref)] = svg_pts[-1]

    # ── Determine label positions for each hole ──
    # For each hole number in hole_stats, find:
    #   - green_pos: where to put the hole number circle
    #   - tee_pos: where to put the stats box
    # Strategy: use ref-keyed data first, then match by proximity to hole lines

    hole_labels: list[dict] = []

    for hole_num in sorted(hole_stats.keys(), key=lambda k: int(k) if str(k).isdigit() else 999):
        ref = str(hole_num)
        stats = hole_stats[hole_num]

        green_pos = green_centroids_by_ref.get(ref)
        tee_pos = tee_centroids_by_ref.get(ref) or hole_line_starts.get(ref)

        # If we have hole line but no green position, use hole line end
        if not green_pos and ref in hole_line_ends:
            green_pos = hole_line_ends[ref]

        # If we have a hole line start but no tee, use that
        if not tee_pos and ref in hole_line_starts:
            tee_pos = hole_line_starts[ref]

        # If we still have neither, try proximity matching:
        # Match to the nearest unmatched green/tee
        if not green_pos and all_green_centroids:
            # Find closest green to any known position for this hole
            anchor = tee_pos or hole_line_starts.get(ref)
            if anchor:
                all_green_centroids.sort(key=lambda g: _dist(g, anchor))
                green_pos = all_green_centroids.pop(0)

        if not tee_pos and all_tee_centroids:
            anchor = green_pos or hole_line_ends.get(ref)
            if anchor:
                all_tee_centroids.sort(key=lambda t: _dist(t, anchor))
                tee_pos = all_tee_centroids.pop(0)

        hole_labels.append({
            "ref": ref,
            "num": int(ref) if str(ref).isdigit() else 0,
            "stats": stats,
            "green_pos": green_pos,
            "tee_pos": tee_pos,
        })

    # ── Per-hole marker groups (hidden/shown by the scorecard based on current hole) ──
    def _marker_attrs(hl: dict) -> str:
        tee = hl.get("tee_pos")
        green = hl.get("green_pos")
        parts = [f'class="hole-marker"', f'data-hole="{hl["ref"]}"']
        if tee:
            parts.append(f'data-tee-x="{_ff(tee[0])}" data-tee-y="{_ff(tee[1])}"')
        if green:
            parts.append(f'data-green-x="{_ff(green[0])}" data-green-y="{_ff(green[1])}"')
        stats = hl.get("stats") or {}
        if stats.get("par") is not None:
            parts.append(f'data-par="{stats.get("par")}"')
        yds = stats.get("yards") or stats.get("yardage")
        if yds:
            parts.append(f'data-yards="{yds}"')
        return " ".join(parts)

    # ── Render per-hole tee badges (only ref-matched tees; unmatched tees
    # stay as anonymous green polygons so they still read as tee boxes.)
    for hl in hole_labels:
        tee = hl.get("tee_pos")
        if not tee:
            continue
        tx, ty = tee
        svg += f'<g {_marker_attrs(hl)}>'
        svg += (
            f'<circle cx="{_ff(tx)}" cy="{_ff(ty)}" r="2.2" '
            f'fill="white" stroke="rgba(0,0,0,0.5)" stroke-width="0.25"/>'
        )
        svg += (
            f'<text x="{_ff(tx)}" y="{_ff(ty + 0.75)}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="2.4" font-family="Arial,sans-serif" '
            f'fill="black" font-weight="bold">{hl["ref"]}</text>'
        )
        svg += '</g>'

    # ── Render green hole-number circles ──
    for hl in hole_labels:
        pos = hl["green_pos"]
        if not pos:
            continue
        cx, cy = pos
        svg += f'<g {_marker_attrs(hl)}>'
        svg += (
            f'<circle cx="{_ff(cx)}" cy="{_ff(cy)}" r="4" '
            f'fill="rgba(0,0,0,0.7)" stroke="white" stroke-width="0.4"/>'
        )
        svg += (
            f'<text x="{_ff(cx)}" y="{_ff(cy + 1.2)}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="4" font-family="Arial,sans-serif" '
            f'fill="white" font-weight="bold">{hl["ref"]}</text>'
        )
        svg += '</g>'

    # ── Render stats boxes near tee positions ──
    for hl in hole_labels:
        tee_pos = hl["tee_pos"]
        # If no tee position, put stats box offset from green
        anchor = tee_pos or hl["green_pos"]
        if not anchor:
            continue

        stats = hl["stats"]
        par = stats.get("par", "")
        yards = stats.get("yards") or stats.get("yardage", "")
        hcp = stats.get("handicap", "")
        if not par and not yards:
            continue

        tx, ty = anchor
        num = hl["num"]
        ref = hl["ref"]

        box_w, box_h = 22, 14
        side = -1 if num % 2 == 0 else 1
        bx = tx + side * 12 - box_w / 2
        by = ty - box_h / 2

        svg += f'<g {_marker_attrs(hl)}>'

        # Connector line
        svg += (
            f'<line x1="{_ff(tx)}" y1="{_ff(ty)}" '
            f'x2="{_ff(bx + box_w / 2)}" y2="{_ff(by + box_h / 2)}" '
            f'stroke="rgba(255,255,255,0.25)" stroke-width="0.3" stroke-dasharray="1,1"/>'
        )

        # Box
        svg += (
            f'<rect x="{_ff(bx)}" y="{_ff(by)}" width="{box_w}" height="{box_h}" '
            f'rx="1.5" fill="rgba(0,0,0,0.75)" stroke="rgba(255,255,255,0.3)" stroke-width="0.3"/>'
        )

        # Hole number circle
        is_odd = num % 2 == 1
        ccx = bx + box_w / 2
        ccy = by + 0.5
        svg += (
            f'<circle cx="{_ff(ccx)}" cy="{_ff(ccy)}" r="3.5" '
            f'fill="{"white" if is_odd else "none"}" '
            f'stroke="white" stroke-width="0.4"/>'
        )
        svg += (
            f'<text x="{_ff(ccx)}" y="{_ff(ccy + 1)}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="3.5" font-family="Arial,sans-serif" '
            f'fill="{"black" if is_odd else "white"}" font-weight="bold">{ref}</text>'
        )

        # Stats line
        line_y = by + 8.5
        fsz = 2.5
        if par:
            svg += (
                f'<text x="{_ff(bx + 2)}" y="{_ff(line_y)}" '
                f'font-size="{fsz}" font-family="Arial,sans-serif" '
                f'fill="rgba(255,255,255,0.85)">P{par}</text>'
            )
        if yards:
            svg += (
                f'<text x="{_ff(bx + box_w / 2)}" y="{_ff(line_y)}" '
                f'text-anchor="middle" '
                f'font-size="{fsz}" font-family="Arial,sans-serif" '
                f'fill="rgba(255,255,255,0.65)">{yards}y</text>'
            )
        if hcp:
            svg += (
                f'<text x="{_ff(bx + box_w - 2)}" y="{_ff(line_y)}" '
                f'text-anchor="end" '
                f'font-size="{fsz}" font-family="Arial,sans-serif" '
                f'fill="rgba(255,255,255,0.5)">H{hcp}</text>'
            )

        svg += '</g>'

    # ── Ball slot (positioned at runtime when a score is entered) ──
    svg += (
        '<g id="ball-layer" style="pointer-events:none">'
        '<circle id="ball-marker" r="1.6" fill="#fff" stroke="#0ea5e9" stroke-width="0.4" '
        'opacity="0"/>'
        '</g>'
    )

    svg += "</svg>"
    return svg


def _ff(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}"
