"""Scoring zone computation — generates zone boundaries per hole."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Default zone ratios (fraction of available space above green)
# +5 is widest (furthest from green), 0 is thinnest (just above green)
DEFAULT_ZONE_RATIOS = {
    5: 0.25,
    4: 0.20,
    3: 0.17,
    2: 0.15,
    1: 0.13,
    0: 0.10,
}

# Minimum zone height in pixels — zones smaller than this get merged
MIN_ZONE_HEIGHT = 8

# Scoring preview colors
ZONE_COLORS = {
    -1: "rgba(0,100,0,0.4)",     # dark green
    0: "rgba(0,180,0,0.3)",      # light green
    1: "rgba(255,255,0,0.3)",    # yellow
    2: "rgba(255,180,0,0.3)",    # orange
    3: "rgba(255,100,0,0.3)",    # red-orange
    4: "rgba(255,50,0,0.3)",     # red
    5: "rgba(180,0,0,0.3)",      # dark red
}


def _find_green_bounds(hole_layout: dict) -> tuple[float, float]:
    """Find the top and bottom y-coordinates of the green features."""
    greens = [f for f in hole_layout.get("features", []) if f.get("category") == "green"]
    if not greens:
        # Fallback: use end_y as green position
        end_y = hole_layout.get("end_y", hole_layout.get("start_y", 0) + 100)
        return end_y - 5, end_y + 5

    green_top = math.inf
    green_bottom = -math.inf
    for g in greens:
        for _, y in g.get("coords", []):
            green_top = min(green_top, y)
            green_bottom = max(green_bottom, y)

    return green_top, green_bottom


def _compute_difficulty_factor(hole_layout: dict) -> float:
    """Compute a difficulty factor that scales zone widths.

    Harder holes (lower handicap/difficulty) get slightly wider zones (more forgiving).
    Returns a multiplier around 1.0 (0.85 for easy, 1.15 for hard).
    """
    difficulty = hole_layout.get("difficulty")
    handicap = hole_layout.get("handicap")

    if handicap is not None:
        # Handicap 1 = hardest → factor 1.15, handicap 18 = easiest → factor 0.85
        return 1.15 - (handicap - 1) * (0.30 / 17)
    if difficulty is not None:
        # difficulty 1 = hardest → 1.15, difficulty 18 = easiest → 0.85
        return 1.15 - (difficulty - 1) * (0.30 / 17)
    return 1.0


def _compute_par_factor(hole_layout: dict) -> float:
    """Par-based zone adjustment. Par 3s are tighter, par 5s more forgiving.

    Returns a multiplier around 1.0.
    """
    par = hole_layout.get("par")
    if par is None:
        return 1.0
    if par <= 3:
        return 0.90  # tighter zones for precision holes
    if par >= 5:
        return 1.10  # more forgiving for long holes
    return 1.0


def _merge_small_zones(zones: list[dict]) -> list[dict]:
    """Merge zones smaller than MIN_ZONE_HEIGHT into adjacent zones.

    Below-green: small +1 merges into +2 (higher/worse score wins).
    Above-green: small zones merge upward toward higher score.
    """
    if not zones:
        return zones

    # Merge below-green zones
    below = [z for z in zones if z.get("position") == "below"]
    if len(below) >= 2:
        total_below = sum(z["y_bottom"] - z["y_top"] for z in below)
        if total_below < MIN_ZONE_HEIGHT:
            # Both too small combined — make one +2 zone
            merged = {
                "score": max(z["score"] for z in below),
                "y_top": below[0]["y_top"],
                "y_bottom": below[-1]["y_bottom"],
                "label": f"+{max(z['score'] for z in below)}",
                "position": "below",
            }
            zones = [z for z in zones if z.get("position") != "below"] + [merged]
        else:
            # Check individual below zones
            small_below = [z for z in below if z["y_bottom"] - z["y_top"] < MIN_ZONE_HEIGHT]
            if small_below:
                # Merge small +1 into +2
                keep = [z for z in below if z not in small_below]
                if keep:
                    # Expand the kept zone to absorb the small ones
                    merged_top = min(z["y_top"] for z in below)
                    merged_bottom = max(z["y_bottom"] for z in below)
                    winner = max(below, key=lambda z: z["score"])
                    merged = {
                        "score": winner["score"],
                        "y_top": merged_top,
                        "y_bottom": merged_bottom,
                        "label": winner["label"],
                        "position": "below",
                    }
                    zones = [z for z in zones if z.get("position") != "below"] + [merged]

    # Merge above-green zones that are too small (merge upward toward higher score)
    above = [z for z in zones if z.get("position") == "above"]
    non_above = [z for z in zones if z.get("position") != "above"]
    merged_above = []
    i = 0
    while i < len(above):
        z = above[i]
        h = z["y_bottom"] - z["y_top"]
        if h < MIN_ZONE_HEIGHT and i > 0:
            # Merge into previous zone (higher score)
            prev = merged_above[-1]
            prev["y_bottom"] = z["y_bottom"]
        elif h < MIN_ZONE_HEIGHT and i < len(above) - 1:
            # Merge into next zone (skip, let next iteration handle)
            nxt = above[i + 1]
            nxt["y_top"] = z["y_top"]
        else:
            merged_above.append(z)
        i += 1

    return merged_above + non_above


def compute_scoring_zones(
    hole_layout: dict,
    available_top: float | None = None,
    available_bottom: float | None = None,
    zone_ratios: dict | None = None,
) -> dict:
    """Compute scoring zones for a hole layout.

    Args:
        hole_layout: hole dict from compute_layout output
        available_top: y-coordinate of top boundary (defaults to start_y - 6)
        available_bottom: y-coordinate of bottom boundary (defaults to end_y + 20)
        zone_ratios: override default narrowing ratios {5: 0.25, 4: 0.20, ...}

    Returns:
        ScoringZoneResult-compatible dict with zones and green bounds.
    """
    start_y = hole_layout.get("start_y", 0)
    end_y = hole_layout.get("end_y", start_y + 100)

    if available_top is None:
        available_top = start_y - 6
    if available_bottom is None:
        available_bottom = end_y + 20

    green_top, green_bottom = _find_green_bounds(hole_layout)
    ratios = zone_ratios or DEFAULT_ZONE_RATIOS

    # Apply difficulty and par factors
    diff_factor = _compute_difficulty_factor(hole_layout)
    par_factor = _compute_par_factor(hole_layout)

    zones = []

    # Zones above green: +5 down to 0
    # Scale above space by difficulty/par factors
    combined_factor = diff_factor * par_factor
    above_space = green_top - available_top
    if above_space > 0:
        # Apply combined factor: harder/longer holes get wider zones
        # Normalize ratios so they sum to 1.0 after scaling
        raw_ratios = {s: ratios.get(s, 0.15) * (combined_factor if s >= 3 else 1.0)
                      for s in [5, 4, 3, 2, 1, 0]}
        total_ratio = sum(raw_ratios.values())
        norm_ratios = {s: r / total_ratio for s, r in raw_ratios.items()}

        cur_y = available_top
        for score in [5, 4, 3, 2, 1, 0]:
            ratio = norm_ratios[score]
            zone_height = above_space * ratio
            zones.append({
                "score": score,
                "y_top": cur_y,
                "y_bottom": cur_y + zone_height,
                "label": f"+{score}" if score > 0 else "0",
                "position": "above",
            })
            cur_y += zone_height

    # Green zone: -1
    zones.append({
        "score": -1,
        "y_top": green_top,
        "y_bottom": green_bottom,
        "label": "-1",
        "position": "green",
    })

    # Zones below green: +1, +2
    below_space = available_bottom - green_bottom
    if below_space > 0:
        half = below_space / 2
        zones.append({
            "score": 1,
            "y_top": green_bottom,
            "y_bottom": green_bottom + half,
            "label": "+1",
            "position": "below",
        })
        zones.append({
            "score": 2,
            "y_top": green_bottom + half,
            "y_bottom": available_bottom,
            "label": "+2",
            "position": "below",
        })

    # Merge zones smaller than MIN_ZONE_HEIGHT
    zones = _merge_small_zones(zones)

    return {
        "hole_ref": hole_layout.get("ref", 0),
        "zones": zones,
        "green_y_top": green_top,
        "green_y_bottom": green_bottom,
    }


def compute_all_scoring_zones(
    layout: dict,
    zone_ratios: dict | None = None,
) -> list[dict]:
    """Compute scoring zones for all holes in a layout.

    Zones tile perfectly — each horizontal slice belongs to exactly one hole.
    The boundary between adjacent holes is the midpoint between the previous
    hole's lowest feature and the next hole's highest feature.
    """
    holes = layout.get("holes", [])
    if not holes:
        return []

    draw_area = layout.get("draw_area", {})
    canvas_top = draw_area.get("top", 0)
    canvas_bottom = draw_area.get("bottom", layout.get("canvas_height", 700))

    # Pre-compute shared boundaries between adjacent holes.
    # Each boundary is the midpoint between the bottom of hole N's features
    # and the top of hole N+1's features. This ensures no overlap and no gaps.
    boundaries = [canvas_top]  # top of first hole = canvas top

    for i in range(len(holes) - 1):
        # Bottom extent of hole i
        hole_i = holes[i]
        i_bottom = hole_i.get("end_y", hole_i["start_y"] + 50)
        for f in hole_i.get("features", []):
            if f.get("category") in ("zone_line", "zone_label"):
                continue
            for _, y in f.get("coords", []):
                i_bottom = max(i_bottom, y)

        # Top extent of hole i+1
        hole_j = holes[i + 1]
        j_top = hole_j.get("start_y", hole_j.get("end_y", i_bottom + 20))
        for f in hole_j.get("features", []):
            if f.get("category") in ("zone_line", "zone_label"):
                continue
            for _, y in f.get("coords", []):
                j_top = min(j_top, y)

        # Shared boundary = midpoint
        boundary = (i_bottom + j_top) / 2
        boundaries.append(boundary)

    boundaries.append(canvas_bottom)  # bottom of last hole = canvas bottom

    results = []
    for i, hole in enumerate(holes):
        avail_top = boundaries[i]
        avail_bottom = boundaries[i + 1]
        result = compute_scoring_zones(hole, avail_top, avail_bottom, zone_ratios)
        results.append(result)

    return results


def add_scoring_features_to_layout(layout: dict, zones_by_hole: list[dict]) -> None:
    """Inject scoring visual elements as synthetic features into the layout.

    Must be called BEFORE warp_layout() so these features get warped
    along with everything else, ensuring alignment.

    Adds two types of synthetic features per hole:
    - zone_line: polylines at zone boundaries (become arcs after warping)
    - zone_label: score number positions for knockout from fairway/water fills
    """
    holes = layout.get("holes", [])

    for hi, hole in enumerate(holes):
        if hi >= len(zones_by_hole):
            continue

        zone_result = zones_by_hole[hi]
        zones = zone_result.get("zones", [])
        # Use ALL zones for boundary lines (above + below green)
        all_zones = zones
        above_zones = [z for z in zones if z.get("position") != "below"]
        if not all_zones:
            continue

        # Get hole's feature x-extent for zone boundary lines
        all_xs = [hole.get("start_x", 0), hole.get("end_x", 0)]
        for f in hole.get("features", []):
            if f.get("category") in ("fairway", "green", "tee", "rough", "water"):
                for pt in f.get("coords", []):
                    all_xs.append(pt[0])
        x_left = min(all_xs)
        x_right = max(all_xs)

        # A. Zone boundary lines for ALL zones (above + below green)
        # Creates lines at each internal boundary and the bottom of the last zone
        n_pts = 25
        for zi in range(1, len(all_zones)):
            y_val = all_zones[zi]["y_top"]
            coords = []
            for j in range(n_pts + 1):
                t = j / n_pts
                x = x_left + t * (x_right - x_left)
                coords.append([x, y_val])
            hole["features"].append({
                "category": "zone_line",
                "coords": coords,
                "score": all_zones[zi]["score"],
                "label": all_zones[zi]["label"],
                "id": None, "ref": None, "par": None, "name": None,
            })
        # Bottom boundary of last zone
        if all_zones:
            last_y = all_zones[-1]["y_bottom"]
            coords = []
            for j in range(n_pts + 1):
                t = j / n_pts
                x = x_left + t * (x_right - x_left)
                coords.append([x, last_y])
            hole["features"].append({
                "category": "zone_line",
                "coords": coords,
                "score": all_zones[-1]["score"],
                "label": f"({all_zones[-1]['label']} bot)",
                "id": None, "ref": None, "par": None, "name": None,
            })

        # B. Score knockout labels — positioned at thickest part of fairway/water
        for zi, zone in enumerate(above_zones):
            score = zone.get("score", 0)
            if score == -1:
                continue  # handled by green polygon knockout
            y_lo = zone["y_top"]
            y_hi = zone["y_bottom"]
            band_h = abs(y_hi - y_lo)
            y_mid = (y_lo + y_hi) / 2
            label = f"{score:+d}" if score != 0 else "0"

            # Find best x-position per filled feature
            for f in hole.get("features", []):
                fcat = f.get("category", "")
                if fcat not in ("fairway", "water"):
                    continue
                coords = f.get("coords", [])
                pts_in_band = [pt for pt in coords if y_lo <= pt[1] <= y_hi]
                if len(pts_in_band) < 2:
                    continue

                f_x_min = min(p[0] for p in pts_in_band)
                f_x_max = max(p[0] for p in pts_in_band)
                f_x_span = f_x_max - f_x_min
                f_x_center = (f_x_min + f_x_max) / 2

                if f_x_span < 0.5:
                    v_span = max(p[1] for p in pts_in_band) - min(p[1] for p in pts_in_band)
                    if v_span >= 1:
                        ko_fs = min(3, max(1.2, min(band_h, v_span) * 0.5))
                        hole["features"].append({
                            "category": "zone_label",
                            "coords": [[f_x_center, y_mid]],
                            "score": score, "label": label,
                            "font_size": ko_fs, "feature_cat": fcat,
                            "id": None, "ref": None, "par": None, "name": None,
                        })
                    continue

                # Sample 15 x-positions, pick thickest with center bias
                n_samples = 15
                margin = max(1.0, f_x_span * 0.15)
                best = None
                for si in range(n_samples):
                    sx = f_x_min + (si + 0.5) * f_x_span / n_samples
                    nearby_y = [p[1] for p in pts_in_band if abs(p[0] - sx) < margin]
                    if len(nearby_y) >= 2:
                        v_span = max(nearby_y) - min(nearby_y)
                        dist = abs(sx - f_x_center) / (f_x_span / 2 + 0.01)
                        bonus = 1.0 + 0.3 * max(0, 1.0 - dist)
                        sc = v_span * bonus
                        if best is None or sc > best["score"]:
                            best = {"x": sx, "v": v_span, "score": sc}

                if best and best["v"] >= 1:
                    ko_fs = min(3, max(1.2, min(band_h, best["v"]) * 0.5))
                    hole["features"].append({
                        "category": "zone_label",
                        "coords": [[best["x"], y_mid]],
                        "score": zone["score"], "label": label,
                        "font_size": ko_fs, "feature_cat": fcat,
                        "id": None, "ref": None, "par": None, "name": None,
                    })


# --- Terrain-following scoring zones ---

@dataclass
class TerrainZone:
    """Legacy terrain zone (kept for backwards compatibility)."""
    score: int
    contour: list
    y_center: float
    y_top: float
    y_bottom: float


@dataclass
class TerrainFollowingZone:
    """Terrain-following zone with polygon boundary and label info."""
    score: int              # -1, 0, 1, 2, 3, 4, 5
    polygon: list           # list of [x, y] points forming the zone boundary
    y_center: float         # vertical center of zone (for ruler alignment)
    y_top: float            # top edge
    y_bottom: float         # bottom edge
    label_position: dict    # {"x": float, "y": float, "inside": bool}
    leader_line: list | None = None  # [(x1,y1), (x2,y2)] if label outside


# Zone width ratios (fraction of remaining hole space from green to tee)
_TF_ZONE_RATIOS = {
    -1: 0.0,   # green polygon itself
    0: 0.05,
    1: 0.05,
    2: 0.10,
    3: 0.15,
    4: 0.25,
    5: 0.35,
}


def _extract_green_polygon(hole_features: list) -> list | None:
    """Extract the green polygon coords from hole features."""
    for f in hole_features:
        if f.get("category") == "green":
            coords = f.get("coords", [])
            if len(coords) >= 3:
                return [list(pt) for pt in coords]
            elif len(coords) > 0:
                cx = sum(p[0] for p in coords) / len(coords)
                cy = sum(p[1] for p in coords) / len(coords)
                r = 5
                return [
                    [cx + r * math.cos(a), cy + r * math.sin(a)]
                    for a in [i * math.pi / 4 for i in range(8)]
                ]
    return None


def _polygon_centroid(poly: list) -> tuple[float, float]:
    """Compute centroid of a polygon."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    return cx, cy


def _polygon_area(poly: list) -> float:
    """Compute area of a polygon using shoelace formula."""
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1]
        area -= poly[j][0] * poly[i][1]
    return abs(area) / 2.0


def _extract_fairway_polygons(hole_features: list) -> list[list]:
    """Extract all fairway polygon coords from hole features."""
    polys = []
    for f in hole_features:
        if f.get("category") == "fairway":
            coords = f.get("coords", [])
            if len(coords) >= 2:
                polys.append([list(pt) for pt in coords])
    return polys


def _fairway_width_at_y(fairway_polys: list, y: float) -> tuple[float | None, float | None]:
    """Find the left and right extent of fairway polygons at a given y.

    Returns (x_left, x_right) or (None, None) if no fairway at this y.
    """
    x_min = math.inf
    x_max = -math.inf
    found = False
    for poly in fairway_polys:
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            y1, y2 = poly[i][1], poly[j][1]
            if (y1 <= y <= y2) or (y2 <= y <= y1):
                if abs(y2 - y1) < 0.001:
                    x_min = min(x_min, poly[i][0], poly[j][0])
                    x_max = max(x_max, poly[i][0], poly[j][0])
                else:
                    t = (y - y1) / (y2 - y1)
                    x_at_y = poly[i][0] + t * (poly[j][0] - poly[i][0])
                    x_min = min(x_min, x_at_y)
                    x_max = max(x_max, x_at_y)
                found = True
    if not found:
        return None, None
    return x_min, x_max


def _offset_polygon_uniform(poly: list, cx: float, cy: float, offset_px: float) -> list:
    """Offset a polygon outward from centroid by a uniform pixel distance."""
    result = []
    for px, py in poly:
        dx = px - cx
        dy = py - cy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.001:
            result.append([px, py])
            continue
        scale = (dist + offset_px) / dist
        result.append([cx + dx * scale, cy + dy * scale])
    return result


def _blend_polygon_with_fairway(
    poly: list, fairway_polys: list, blend_factor: float,
    routing_cx: float, fallback_half_w: float,
) -> list:
    """Blend a polygon's lateral bounds toward fairway edges.

    blend_factor: 0 = keep polygon shape, 1 = fully match fairway width.
    """
    if blend_factor <= 0 or not fairway_polys:
        return poly

    result = []
    for px, py in poly:
        fw_left, fw_right = _fairway_width_at_y(fairway_polys, py)
        if fw_left is None:
            # No fairway at this y: widen gently from routing center
            fw_left = routing_cx - fallback_half_w
            fw_right = routing_cx + fallback_half_w

        # Determine if point is on left or right of routing center
        if px < routing_cx:
            target_x = fw_left
        else:
            target_x = fw_right
        new_x = px + blend_factor * (target_x - px)
        result.append([new_x, py])
    return result


def compute_terrain_following_zones(
    hole_layout: dict,
    available_top: float,
    available_bottom: float,
    zone_ratios: dict | None = None,
) -> list[TerrainFollowingZone]:
    """Compute terrain-following scoring zones for a hole.

    Zones radiate outward from the green following fairway shape.
    Returns TerrainFollowingZone objects with polygon boundaries.
    """
    features = hole_layout.get("features", [])
    ratios = zone_ratios or _TF_ZONE_RATIOS

    green_poly = _extract_green_polygon(features)
    if green_poly is None:
        # Fallback: small ellipse at end position
        cx = hole_layout.get("end_x", hole_layout.get("start_x", 100))
        cy = hole_layout.get("end_y", hole_layout.get("start_y", 100) + 100)
        r = 5
        green_poly = [
            [cx + r * math.cos(a), cy + r * math.sin(a)]
            for a in [i * math.pi / 4 for i in range(8)]
        ]

    gcx, gcy = _polygon_centroid(green_poly)
    fairway_polys = _extract_fairway_polygons(features)

    # Tee centroid for routing direction
    tee_features = [f for f in features if f.get("category") == "tee"]
    if tee_features and tee_features[0].get("coords"):
        tee_coords = tee_features[0]["coords"]
        tcx = sum(p[0] for p in tee_coords) / len(tee_coords)
        tcy = sum(p[1] for p in tee_coords) / len(tee_coords)
    else:
        tcx = gcx
        tcy = available_top

    # Available space from green to tee area
    above_space = gcy - available_top
    if above_space <= 5:
        above_space = 50

    # Compute feature x-extent for fallback widening
    all_xs = [gcx]
    for f in features:
        for px, _ in f.get("coords", []):
            all_xs.append(px)
    feature_half_w = (max(all_xs) - min(all_xs)) / 2 + 10

    zones: list[TerrainFollowingZone] = []

    # -1 zone: the green polygon itself
    green_ys = [p[1] for p in green_poly]
    green_area = _polygon_area(green_poly)
    inside = green_area > 100
    lp_x, lp_y = gcx, gcy
    zones.append(TerrainFollowingZone(
        score=-1,
        polygon=[list(p) for p in green_poly],
        y_center=gcy,
        y_top=min(green_ys),
        y_bottom=max(green_ys),
        label_position={"x": lp_x, "y": lp_y, "inside": inside},
        leader_line=None if inside else [[lp_x + 15, lp_y - 5], [lp_x, lp_y]],
    ))

    # Build zones 0 through 5 as progressively larger offsets from green
    cumulative_offset = 3.0  # initial gap around green for zone 0
    prev_polygon = green_poly

    for score in [0, 1, 2, 3, 4, 5]:
        ratio = ratios.get(score, 0.15)
        zone_height = above_space * ratio

        # Offset from green centroid
        offset_px = cumulative_offset
        polygon = _offset_polygon_uniform(green_poly, gcx, gcy, offset_px)

        # Blend with fairway bounds for outer zones
        blend = 0.0
        if score >= 2:
            blend = min(1.0, (score - 1) * 0.25)  # +2: 0.25, +3: 0.5, +4: 0.75, +5: 1.0
        if blend > 0:
            # Widen fallback based on distance from green
            widen = feature_half_w * (1 + score * 0.15)
            polygon = _blend_polygon_with_fairway(
                polygon, fairway_polys, blend, gcx, widen
            )

        # Clamp vertical bounds
        polygon = [[p[0], max(available_top, min(available_bottom, p[1]))] for p in polygon]

        ys = [p[1] for p in polygon]
        y_center = sum(ys) / len(ys) if ys else gcy
        y_top = min(ys) if ys else gcy
        y_bottom = max(ys) if ys else gcy

        # Label position
        area = _polygon_area(polygon)
        inside = area > 100
        lp_x, lp_y = _polygon_centroid(polygon)
        leader = None
        if not inside:
            # Place label outside to the right with leader line
            max_x = max(p[0] for p in polygon)
            lp_x = max_x + 12
            lp_y = y_center
            closest_x = max(p[0] for p in polygon if abs(p[1] - y_center) < zone_height / 2 + 5)
            leader = [[lp_x - 2, lp_y], [closest_x, lp_y]]

        zones.append(TerrainFollowingZone(
            score=score,
            polygon=polygon,
            y_center=y_center,
            y_top=y_top,
            y_bottom=y_bottom,
            label_position={"x": lp_x, "y": lp_y, "inside": inside},
            leader_line=leader,
        ))

        cumulative_offset += zone_height

    return zones


def compute_all_terrain_following_zones(
    layout: dict,
    zone_ratios: dict | None = None,
) -> list[list[TerrainFollowingZone]]:
    """Compute terrain-following zones for all holes in a layout."""
    holes = layout.get("holes", [])
    if not holes:
        return []

    draw_area = layout.get("draw_area", {})
    canvas_top = draw_area.get("top", 0)
    canvas_bottom = draw_area.get("bottom", layout.get("canvas_height", 700))

    results = []
    for i, hole in enumerate(holes):
        # Top boundary
        if i == 0:
            avail_top = canvas_top
        else:
            prev = holes[i - 1]
            prev_bottom = prev["start_y"] + 14
            for f in prev.get("features", []):
                for _, y in f.get("coords", []):
                    prev_bottom = max(prev_bottom, y)
            avail_top = prev_bottom + 2

        # Bottom boundary
        if i == len(holes) - 1:
            avail_bottom = canvas_bottom
        else:
            nxt = holes[i + 1]
            nxt_top = nxt["start_y"] - 2
            for f in nxt.get("features", []):
                for _, y in f.get("coords", []):
                    nxt_top = min(nxt_top, y)
            avail_bottom = nxt_top - 2

        tf_zones = compute_terrain_following_zones(hole, avail_top, avail_bottom, zone_ratios)
        results.append(tf_zones)

    return results
