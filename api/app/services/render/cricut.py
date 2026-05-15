"""Cricut 3-color SVG export — white, green, and tan vinyl layers."""
from __future__ import annotations

import math


def _ff(n: float) -> str:
    return f"{n:.2f}"


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


def _bbox(coords: list[list[float]]) -> dict:
    """Compute bounding box for a list of coordinates."""
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return {
        "min_x": min(xs), "max_x": max(xs),
        "min_y": min(ys), "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def _scale_ruler_element(x: float, y: float) -> str:
    """Generate a 10mm scale verification ruler element."""
    bar_width = 10  # 10mm
    bar_height = 1.5
    return (
        f'<g transform="translate({_ff(x)}, {_ff(y)})">'
        f'<rect x="0" y="0" width="{_ff(bar_width)}" height="{_ff(bar_height)}" '
        f'fill="none" stroke="black" stroke-width="0.3"/>'
        f'<line x1="0" y1="0" x2="0" y2="{_ff(bar_height + 1)}" stroke="black" stroke-width="0.2"/>'
        f'<line x1="{_ff(bar_width)}" y1="0" x2="{_ff(bar_width)}" y2="{_ff(bar_height + 1)}" '
        f'stroke="black" stroke-width="0.2"/>'
        f'<text x="{_ff(bar_width / 2)}" y="{_ff(bar_height + 3.5)}" text-anchor="middle" '
        f'font-size="2" font-family="Arial" fill="black">10mm — print at 100% scale</text>'
        f'</g>'
    )


def _px_to_mm(px: float, template: dict) -> float:
    """Convert pixel coordinate to mm using glass template scale."""
    # The glass slant_height in mm maps to outer_r - inner_r in layout units
    slant_mm = template.get("slant_height", 150)
    radial_range = template.get("outer_r", 500) - template.get("inner_r", 350)
    if radial_range <= 0:
        return px * 0.3  # fallback
    return px * (slant_mm / radial_range)


def _extract_features_by_category(layout: dict, categories: set) -> list[dict]:
    """Extract all features of given categories from all holes, with hole ref."""
    pieces = []
    for hole in layout.get("holes", []):
        hole_ref = hole.get("ref", 0)
        for feat in hole.get("features", []):
            if feat.get("category") in categories:
                coords = feat.get("coords", [])
                if len(coords) >= 2:
                    pieces.append({
                        "hole_ref": hole_ref,
                        "category": feat["category"],
                        "coords": coords,
                        "id": feat.get("id", ""),
                    })
    return pieces


def _compact_arrange(pieces: list[dict], canvas_width: float = 200,
                     padding: float = 5) -> list[dict]:
    """Arrange pieces in compact rows for efficient vinyl cutting.

    Sort by height descending, place left-to-right in rows.
    Returns pieces with translated coordinates and placement info.
    """
    if not pieces:
        return []

    # Compute bounding boxes and normalize each piece to origin
    arranged = []
    for piece in pieces:
        bb = _bbox(piece["coords"])
        arranged.append({
            **piece,
            "bbox": bb,
            "norm_coords": [[x - bb["min_x"], y - bb["min_y"]] for x, y in piece["coords"]],
        })

    # Sort by height descending (tall pieces first for better packing)
    arranged.sort(key=lambda p: p["bbox"]["height"], reverse=True)

    # Pack into rows
    cur_x = padding
    cur_y = padding
    row_height = 0

    for piece in arranged:
        w = piece["bbox"]["width"]
        h = piece["bbox"]["height"]

        # Wrap to next row if needed
        if cur_x + w + padding > canvas_width and cur_x > padding:
            cur_y += row_height + padding
            cur_x = padding
            row_height = 0

        # Place piece at (cur_x, cur_y)
        piece["placed_x"] = cur_x
        piece["placed_y"] = cur_y
        piece["placed_coords"] = [[x + cur_x, y + cur_y] for x, y in piece["norm_coords"]]

        cur_x += w + padding
        row_height = max(row_height, h)

    total_height = cur_y + row_height + padding
    for piece in arranged:
        piece["canvas_height"] = total_height

    return arranged


def render_cricut_white(layout: dict, zones_by_hole: list[dict],
                        template: dict | None = None, opts: dict | None = None,
                        terrain_zones: list | None = None) -> str:
    """Render white vinyl layer — uses same rendering as glass preview."""
    from app.services.render.svg import _render_vinyl_preview

    render_opts = dict(opts or {})
    render_opts["zones_by_hole"] = zones_by_hole
    render_opts["terrain_zones"] = terrain_zones or []
    render_opts["is_warped"] = layout.get("warped") and layout.get("template")
    render_opts["vinyl_preview"] = True

    return _render_vinyl_preview(layout, render_opts, layer="white")


def render_cricut_green(layout: dict, opts: dict | None = None,
                        zones_by_hole: list | None = None) -> str:
    """Render green vinyl layer — delegates to shared vinyl preview renderer."""
    from app.services.render.svg import _render_vinyl_preview
    opts = opts or {}
    render_opts = {**opts, "vinyl_preview": True, "zones_by_hole": zones_by_hole or []}
    return _render_vinyl_preview(layout, render_opts, layer="green")


def render_cricut_tan(layout: dict, opts: dict | None = None) -> str:
    """Render tan vinyl layer — delegates to shared vinyl preview renderer."""
    from app.services.render.svg import _render_vinyl_preview
    opts = opts or {}
    render_opts = {**opts, "vinyl_preview": True, "zones_by_hole": []}
    return _render_vinyl_preview(layout, render_opts, layer="tan")


def render_cricut_blue(layout: dict, opts: dict | None = None) -> str:
    """Render blue vinyl layer — delegates to shared vinyl preview renderer."""
    from app.services.render.svg import _render_vinyl_preview
    opts = opts or {}
    render_opts = {**opts, "vinyl_preview": True, "zones_by_hole": []}
    return _render_vinyl_preview(layout, render_opts, layer="blue")


def render_cricut_green_inplace(layout: dict, opts: dict | None = None) -> str:
    """Render green elements in glass layout positions (not compact)."""
    from app.services.render.svg import _render_vinyl_preview
    render_opts = dict(opts or {})
    render_opts["vinyl_preview"] = True
    render_opts["zones_by_hole"] = []
    render_opts["terrain_zones"] = []
    return _render_vinyl_preview(layout, render_opts, layer="green")


def render_cricut_blue_inplace(layout: dict, opts: dict | None = None) -> str:
    """Render blue elements in glass layout positions (not compact)."""
    from app.services.render.svg import _render_vinyl_preview
    render_opts = dict(opts or {})
    render_opts["vinyl_preview"] = True
    render_opts["zones_by_hole"] = []
    render_opts["terrain_zones"] = []
    return _render_vinyl_preview(layout, render_opts, layer="blue")


def render_cricut_tan_inplace(layout: dict, opts: dict | None = None) -> str:
    """Render tan elements in glass layout positions (not compact)."""
    from app.services.render.svg import _render_vinyl_preview
    render_opts = dict(opts or {})
    render_opts["vinyl_preview"] = True
    render_opts["zones_by_hole"] = []
    render_opts["terrain_zones"] = []
    return _render_vinyl_preview(layout, render_opts, layer="tan")


def render_cricut_combined(layout: dict, zones_by_hole: list[dict],
                            template: dict | None = None, opts: dict | None = None,
                            terrain_zones: list | None = None) -> str:
    """Render all color layers into a single SVG (full glass preview)."""
    from app.services.render.svg import _render_vinyl_preview

    render_opts = dict(opts or {})
    render_opts["zones_by_hole"] = zones_by_hole
    render_opts["terrain_zones"] = terrain_zones or []
    render_opts["is_warped"] = layout.get("warped") and layout.get("template")
    render_opts["vinyl_preview"] = True

    return _render_vinyl_preview(layout, render_opts, layer="all")


def render_cricut_guide(layout: dict, opts: dict | None = None) -> str:
    """Render placement guide SVG showing where green/tan pieces go on the glass."""
    opts = opts or {}
    font_family = opts.get("font_family", "Arial")
    is_warped = layout.get("warped") and layout.get("template")

    if is_warped:
        t = layout["template"]
        half_a = t["sector_angle"] / 2
        pad = 5
        vb_x = -t["outer_r"] * math.sin(half_a) - pad
        vb_y = -t["outer_r"] - pad
        vb_w = 2 * t["outer_r"] * math.sin(half_a) + pad * 2
        vb_h = t["outer_r"] - t["inner_r"] * math.cos(half_a) + pad * 2
    else:
        vb_x, vb_y = 0, 0
        vb_w = layout.get("canvas_width", 900)
        vb_h = layout.get("canvas_height", 700)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{_ff(vb_x)} {_ff(vb_y)} {_ff(vb_w)} {_ff(vb_h)}" '
        f'width="{round(vb_w)}" height="{round(vb_h)}">'
    )

    # Glass outline
    if is_warped:
        from app.services.render.glass_template import glass_wrap_path
        svg += (
            f'<path d="{glass_wrap_path(layout["template"])}" fill="none" '
            f'stroke="#888" stroke-width="0.5" stroke-dasharray="3,2"/>'
        )

    # Draw all features with color coding and labels
    color_map = {
        "green": "#00cc00",
        "tee": "#00aa00",
        "bunker": "#c4a035",
        "fairway": "#666",
        "rough": "#444",
        "water": "#3b82f6",
    }

    for hole in layout.get("holes", []):
        ref = hole.get("ref", 0)
        for feat in hole.get("features", []):
            cat = feat.get("category", "")
            color = color_map.get(cat, "#888")
            d = _coords_to_path(feat.get("coords", []))
            if not d:
                continue

            is_colored_piece = cat in ("green", "tee", "bunker", "water")
            sw = "0.8" if is_colored_piece else "0.3"
            opacity = "0.9" if is_colored_piece else "0.3"

            svg += (
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{sw}" opacity="{opacity}"/>'
            )

            # Label colored pieces
            if is_colored_piece:
                bb = _bbox(feat.get("coords", [[0, 0]]))
                lx = (bb["min_x"] + bb["max_x"]) / 2
                ly = (bb["min_y"] + bb["max_y"]) / 2
                prefix = {"green": "G", "tee": "T", "bunker": "B", "water": "W"}[cat]
                svg += (
                    f'<text x="{_ff(lx)}" y="{_ff(ly + 1)}" text-anchor="middle" '
                    f'fill="{color}" font-size="3" font-weight="700" '
                    f'font-family="{font_family}">{prefix}{ref}</text>'
                )

    svg += "</svg>"
    return svg
