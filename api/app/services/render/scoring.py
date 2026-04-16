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

# Minimum zone height in pixels — zones smaller than this get merged.
# Also used as the threshold for dropping high-score zones on short holes
# so that remaining zones are legible after warping onto the glass.
MIN_ZONE_HEIGHT = 15

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
        if h < MIN_ZONE_HEIGHT and merged_above:
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
    next_tee_top: float | None = None,
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

    # Zones above green: scores from max_score down to 0.
    # Max score is par-based: par 3 → +3, par 4 → +4, par 5+ → +5.
    # If the available vertical space is too small for that many zones,
    # drop the highest scores until each zone meets the minimum height.
    par = hole_layout.get("par") or 4
    max_score = min(par, 5)

    combined_factor = diff_factor * par_factor
    above_space = green_top - available_top
    if above_space > 0:
        # Reduce zones until each one meets the minimum height threshold
        min_zone_h = MIN_ZONE_HEIGHT
        while max_score > 1 and above_space / (max_score + 1) < min_zone_h:
            max_score -= 1

        score_list = list(range(max_score, -1, -1))  # e.g. [3, 2, 1, 0]

        # Apply combined factor: harder/longer holes get wider zones
        raw_ratios = {s: ratios.get(s, 0.15) * (combined_factor if s >= 3 else 1.0)
                      for s in score_list}
        total_ratio = sum(raw_ratios.values())
        norm_ratios = {s: r / total_ratio for s, r in raw_ratios.items()}

        cur_y = available_top
        for score in score_list:
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

    # Zones below green: +1 (green to next tee), +2 (over next tee area)
    below_space = available_bottom - green_bottom
    if below_space > 0:
        if next_tee_top is not None and next_tee_top > green_bottom:
            # +1 from green bottom to next tee top
            zones.append({
                "score": 1,
                "y_top": green_bottom,
                "y_bottom": next_tee_top,
                "label": "+1",
                "position": "below",
            })
            # +2 from next tee top to boundary (over the tee box)
            if available_bottom > next_tee_top:
                zones.append({
                    "score": 2,
                    "y_top": next_tee_top,
                    "y_bottom": available_bottom,
                    "label": "+2",
                    "position": "below",
                })
        else:
            # Last hole on glass or no next tee: split evenly
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

    # Two-pass layout: compute zones for each pass independently
    if layout.get("layout_mode") == "two_column":
        split = layout.get("column_split", len(holes) // 2)
        pass1_holes = holes[:split]
        pass2_holes = holes[split:]
        # Build sub-layouts for each pass
        sub1 = {**layout, "holes": pass1_holes}
        sub2 = {**layout, "holes": pass2_holes}
        # Remove layout_mode to avoid infinite recursion
        sub1.pop("layout_mode", None)
        sub2.pop("layout_mode", None)
        results1 = compute_all_scoring_zones(sub1, zone_ratios)
        results2 = compute_all_scoring_zones(sub2, zone_ratios)
        return results1 + results2

    draw_area = layout.get("draw_area", {})
    canvas_top = draw_area.get("top", 0)
    canvas_bottom = draw_area.get("bottom", layout.get("canvas_height", 700))

    # Pre-compute shared boundaries between adjacent holes.
    # Boundaries extend past the next hole's tee so that the previous hole's
    # below-green zones (+1, +2) can overlap into the next tee area.
    # The next hole's +5 zone starts immediately after.
    boundaries = [canvas_top]  # top of first hole = canvas top

    # Also track next-tee-top for each hole (used for +1/+2 split)
    next_tee_tops = []

    for i in range(len(holes) - 1):
        hole_j = holes[i + 1]

        # Find top of next hole's tee features
        j_tee_top = hole_j.get("start_y", hole_j.get("end_y", 0))
        for f in hole_j.get("features", []):
            if f.get("category") == "tee":
                for _, y in f.get("coords", []):
                    j_tee_top = min(j_tee_top, y)

        # Find bottom of next hole's tee features
        j_tee_bottom = hole_j.get("start_y", hole_j.get("end_y", 0))
        for f in hole_j.get("features", []):
            if f.get("category") == "tee":
                for _, y in f.get("coords", []):
                    j_tee_bottom = max(j_tee_bottom, y)

        next_tee_tops.append(j_tee_top)

        # Boundary extends past the next hole's tee
        boundary = j_tee_bottom + 5
        boundaries.append(boundary)

    next_tee_tops.append(None)  # last hole has no next tee
    boundaries.append(canvas_bottom)  # bottom of last hole = canvas bottom

    results = []
    for i, hole in enumerate(holes):
        avail_top = boundaries[i]
        avail_bottom = boundaries[i + 1]
        result = compute_scoring_zones(
            hole, avail_top, avail_bottom, zone_ratios,
            next_tee_top=next_tee_tops[i],
        )
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

            # Two-pass approach: first try knockouts in all features,
            # then only create external labels if no knockout was placed.
            has_knockout = False
            pending_externals = []

            for f in hole.get("features", []):
                fcat = f.get("category", "")
                if fcat not in ("fairway", "water"):
                    continue
                coords = f.get("coords", [])
                if len(coords) < 3:
                    continue

                # Build polygon edges for distance checks
                n_edges = len(coords)
                edges = []
                for ei in range(n_edges):
                    ej = (ei + 1) % n_edges
                    edges.append((coords[ei], coords[ej]))

                # Bounding box of feature clipped to band
                all_x = [p[0] for p in coords]
                all_y = [p[1] for p in coords]
                clip_y_lo = max(y_lo, min(all_y))
                clip_y_hi = min(y_hi, max(all_y))
                if clip_y_hi - clip_y_lo < 0.5:
                    continue
                clip_x_lo = min(all_x)
                clip_x_hi = max(all_x)
                if clip_x_hi - clip_x_lo < 0.5:
                    continue

                # Sample a grid of candidate points
                n_x, n_y = 15, 10

                def _pt_in_poly(cx, cy):
                    inside = False
                    for (ax, ay), (bx, by) in edges:
                        if (ay > cy) != (by > cy):
                            ix = ax + (cy - ay) / (by - ay) * (bx - ax)
                            if cx < ix:
                                inside = not inside
                    return inside

                def _min_edge_dist(cx, cy):
                    min_d = min(abs(cy - y_lo), abs(cy - y_hi))
                    for (ax, ay), (bx, by) in edges:
                        dx, dy = bx - ax, by - ay
                        if dx == 0 and dy == 0:
                            d = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
                        else:
                            t = max(0, min(1, ((cx - ax) * dx + (cy - ay) * dy) / (dx * dx + dy * dy)))
                            px, py = ax + t * dx, ay + t * dy
                            d = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                        if d < min_d:
                            min_d = d
                    return min_d

                # Pass 1: find centroid of all interior grid points (visual center of mass)
                interior_pts = []
                for yi in range(n_y):
                    cy = clip_y_lo + (yi + 0.5) * (clip_y_hi - clip_y_lo) / n_y
                    for xi in range(n_x):
                        cx = clip_x_lo + (xi + 0.5) * (clip_x_hi - clip_x_lo) / n_x
                        if _pt_in_poly(cx, cy):
                            interior_pts.append((cx, cy))

                if not interior_pts:
                    continue

                centroid_x = sum(p[0] for p in interior_pts) / len(interior_pts)
                centroid_y = sum(p[1] for p in interior_pts) / len(interior_pts)

                # Pass 2: pick the point with best edge clearance, biased toward centroid.
                # Score = edge_distance - penalty for distance from centroid
                best_pt = None
                best_score = -999
                for cx, cy in interior_pts:
                    ed = _min_edge_dist(cx, cy)
                    # Penalty: distance from centroid — stronger pull toward center
                    cd = ((cx - centroid_x) ** 2 + (cy - centroid_y) ** 2) ** 0.5
                    penalty = cd * 0.5
                    sc = ed - penalty
                    if sc > best_score:
                        best_score = sc
                        best_pt = (cx, cy)
                        best_dist = ed

                min_clearance = 1.5
                if best_pt and best_dist >= min_clearance:
                    ko_fs = min(2, max(1, best_dist * 0.5))
                    hole["features"].append({
                        "category": "zone_label",
                        "coords": [[best_pt[0], best_pt[1]]],
                        "score": zone["score"], "label": label,
                        "font_size": ko_fs, "feature_cat": fcat,
                        "id": None, "ref": None, "par": None, "name": None,
                    })
                    has_knockout = True
                else:
                    # Zone too small — queue external label (only used if no knockout placed)
                    anchor_x, anchor_y = centroid_x, centroid_y
                    nearest_edge_x, nearest_edge_y = anchor_x, anchor_y
                    nearest_d = float("inf")
                    for (ax, ay), (bx, by) in edges:
                        dx, dy = bx - ax, by - ay
                        if dx == 0 and dy == 0:
                            continue
                        t = max(0, min(1, ((anchor_x - ax) * dx + (anchor_y - ay) * dy) / (dx * dx + dy * dy)))
                        px, py = ax + t * dx, ay + t * dy
                        d = ((anchor_x - px) ** 2 + (anchor_y - py) ** 2) ** 0.5
                        if d < nearest_d:
                            nearest_d = d
                            nearest_edge_x, nearest_edge_y = px, py
                    dir_x = nearest_edge_x - anchor_x
                    dir_y = nearest_edge_y - anchor_y
                    dir_len = (dir_x ** 2 + dir_y ** 2) ** 0.5
                    if dir_len > 0.01:
                        dir_x /= dir_len
                        dir_y /= dir_len
                    else:
                        dir_x, dir_y = 1, 0
                    ext_x = nearest_edge_x + dir_x * 8
                    ext_y = nearest_edge_y + dir_y * 8
                    pending_externals.append({
                        "category": "zone_label_external",
                        "coords": [[ext_x, ext_y], [nearest_edge_x, nearest_edge_y]],
                        "score": zone["score"], "label": label,
                        "font_size": 1.8, "feature_cat": fcat,
                        "id": None, "ref": None, "par": None, "name": None,
                    })

            # Only add external labels if no knockout was placed for this score
            if not has_knockout and pending_externals:
                # Just add the first one (avoid duplicates)
                hole["features"].append(pending_externals[0])


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

        # Label position — find widest part of the BAND between this and prev polygon
        area = _polygon_area(polygon)
        inside = area > 100
        lp_x, lp_y = _polygon_centroid(polygon)
        best_band_w = 0

        def _x_extents_at_y(poly, test_y):
            """Get min/max x of polygon at a given y via edge intersections."""
            xs = []
            for pi2 in range(len(poly)):
                pj2 = (pi2 + 1) % len(poly)
                py0, py1 = poly[pi2][1], poly[pj2][1]
                if (py0 <= test_y <= py1) or (py1 <= test_y <= py0):
                    if py1 != py0:
                        t = (test_y - py0) / (py1 - py0)
                        xs.append(poly[pi2][0] + t * (poly[pj2][0] - poly[pi2][0]))
            if len(xs) >= 2:
                return min(xs), max(xs)
            return None

        for frac_i in range(1, 20):
            test_y = y_top + (frac_i / 20) * (y_bottom - y_top)
            outer = _x_extents_at_y(polygon, test_y)
            if not outer:
                continue
            inner = _x_extents_at_y(prev_polygon, test_y)
            if inner:
                # Band is the outer polygon minus inner polygon
                # Use the side (left or right) with more band width
                left_band = inner[0] - outer[0]
                right_band = outer[1] - inner[1]
                if left_band > right_band and left_band > best_band_w:
                    best_band_w = left_band
                    lp_x = (outer[0] + inner[0]) / 2
                    lp_y = test_y
                elif right_band >= left_band and right_band > best_band_w:
                    best_band_w = right_band
                    lp_x = (outer[1] + inner[1]) / 2
                    lp_y = test_y
            else:
                # prev polygon doesn't reach this y — full outer width is the band
                w = outer[1] - outer[0]
                if w > best_band_w:
                    best_band_w = w
                    lp_x = (outer[0] + outer[1]) / 2
                    lp_y = test_y

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
            label_position={"x": lp_x, "y": lp_y, "inside": inside, "zone_h": zone_height, "zone_w": best_band_w},
            leader_line=leader,
        ))

        prev_polygon = polygon
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

    # Two-column layout: compute each column independently
    if layout.get("layout_mode") == "two_column":
        split = layout.get("column_split", len(holes) // 2)
        sub1 = {**layout, "holes": holes[:split]}
        sub2 = {**layout, "holes": holes[split:]}
        sub1.pop("layout_mode", None)
        sub2.pop("layout_mode", None)
        return (compute_all_terrain_following_zones(sub1, zone_ratios)
                + compute_all_terrain_following_zones(sub2, zone_ratios))

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

        # Bottom boundary — extend past the next hole's tee
        if i == len(holes) - 1:
            avail_bottom = canvas_bottom
        else:
            nxt = holes[i + 1]
            nxt_tee_bottom = nxt["start_y"]
            for f in nxt.get("features", []):
                if f.get("category") == "tee":
                    for _, y in f.get("coords", []):
                        nxt_tee_bottom = max(nxt_tee_bottom, y)
            avail_bottom = nxt_tee_bottom + 5

        tf_zones = compute_terrain_following_zones(hole, avail_top, avail_bottom, zone_ratios)
        results.append(tf_zones)

    return results
