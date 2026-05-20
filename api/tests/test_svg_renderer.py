"""Tests for SVG renderer."""

from app.services.render.svg import (
    render_svg,
    _hex_to_rgb,
    _rgb_to_hsl,
    _hsl_to_rgb,
    _tint_color,
    _coords_to_path,
    _ff,
    _esc_xml,
)


class TestColorUtils:
    def test_hex_to_rgb(self):
        assert _hex_to_rgb("#ff0000") == {"r": 255, "g": 0, "b": 0}
        assert _hex_to_rgb("#000") == {"r": 0, "g": 0, "b": 0}

    def test_rgb_to_hsl_red(self):
        hsl = _rgb_to_hsl(255, 0, 0)
        assert hsl["h"] == 0
        assert abs(hsl["s"] - 1.0) < 0.01

    def test_hsl_to_rgb_roundtrip(self):
        rgb = _hsl_to_rgb(120, 0.5, 0.5)
        assert 0 <= rgb["r"] <= 255
        assert rgb["g"] > rgb["r"]  # green is dominant

    def test_tint_color_none(self):
        assert _tint_color("none", 120, 0.35) == "none"

    def test_tint_color_rgba(self):
        assert _tint_color("rgba(0,0,0,0.5)", 120, 0.35) == "rgba(0,0,0,0.5)"

    def test_tint_color_hex(self):
        result = _tint_color("#4a8f3f", 120, 0.35)
        assert result.startswith("rgb(")


class TestHelpers:
    def test_ff(self):
        assert _ff(3.14159) == "3.1"
        assert _ff(0.0) == "0.0"

    def test_esc_xml(self):
        assert _esc_xml("a&b") == "a&amp;b"
        assert _esc_xml("<test>") == "&lt;test&gt;"
        assert _esc_xml(None) == ""

    def test_coords_to_path_closed(self):
        path = _coords_to_path([[0, 0], [10, 10], [20, 0]], True)
        assert path.startswith("M0.0,0.0")
        assert path.endswith("Z")

    def test_coords_to_path_open(self):
        path = _coords_to_path([[0, 0], [10, 10]], False)
        assert "Z" not in path

    def test_coords_to_path_empty(self):
        assert _coords_to_path([], True) == ""
        assert _coords_to_path([[0, 0]], True) == ""


class TestRenderSvg:
    def _make_layout(self):
        return {
            "holes": [
                {
                    "ref": 1,
                    "par": 4,
                    "start_x": 200,
                    "start_y": 50,
                    "end_x": 300,
                    "end_y": 200,
                    "direction": 1,
                    "features": [
                        {"category": "fairway", "coords": [[200, 80], [250, 150], [300, 180]]},
                        {"category": "green", "coords": [[280, 190], [300, 200], [310, 195]]},
                        {"category": "tee", "coords": [[190, 50], [210, 55]]},
                    ],
                },
            ],
            "canvas_width": 900,
            "canvas_height": 700,
        }

    def test_basic_render(self):
        svg = render_svg(self._make_layout())
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert 'viewBox="' in svg

    def test_contains_feature_layers(self):
        svg = render_svg(self._make_layout())
        assert 'class="layer-fairway"' in svg
        assert 'class="layer-green"' in svg
        assert 'class="layer-tee"' in svg

    def test_contains_hole_number(self):
        svg = render_svg(self._make_layout())
        assert 'class="layer-hole_number"' in svg
        assert ">1</text>" in svg

    def test_contains_par_label(self):
        svg = render_svg(self._make_layout())
        assert "P4</text>" in svg

    def test_hidden_layers(self):
        svg = render_svg(self._make_layout(), {"hidden_layers": ["background", "rough"]})
        assert 'fill="#1a472a"' not in svg  # background hidden
        assert 'class="layer-rough"' not in svg

    def test_custom_font(self):
        svg = render_svg(self._make_layout(), {"font_family": "Georgia"})
        assert 'font-family="Georgia"' in svg

    def test_course_name_rect(self):
        svg = render_svg(self._make_layout(), {"course_name": "Pebble Beach"})
        assert "PEBBLE BEACH" in svg

    def test_empty_layout(self):
        svg = render_svg({"holes": [], "canvas_width": 900, "canvas_height": 700})
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_warped_mode(self):
        from app.services.render.glass_template import compute_glass_template, warp_layout
        layout = self._make_layout()
        template = compute_glass_template()
        warped = warp_layout(layout, template)
        svg = render_svg(warped)
        assert svg.startswith("<svg")
        assert "glassClip" in svg

    def test_hole_stats_layer(self):
        svg = render_svg(self._make_layout())
        assert 'class="layer-hole_stats"' in svg

    def test_hole_stats_hidden(self):
        svg = render_svg(self._make_layout(), {"hidden_layers": ["hole_stats"]})
        assert 'class="layer-hole_stats"' not in svg

    def test_ruler_with_zones(self):
        layout = self._make_layout()
        layout["draw_area"] = {"left": 60, "right": 870, "top": 30, "bottom": 670}
        zones = [{
            "hole_ref": 1,
            "zones": [
                {"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"},
                {"score": -1, "y_top": 180, "y_bottom": 200, "label": "-1", "position": "green"},
            ],
            "green_y_top": 180,
            "green_y_bottom": 200,
        }]
        svg = render_svg(layout, {"zones_by_hole": zones})
        assert 'class="layer-ruler"' in svg
        assert "+5" in svg

    def test_ruler_hidden(self):
        layout = self._make_layout()
        layout["draw_area"] = {"left": 60, "right": 870, "top": 30, "bottom": 670}
        zones = [{
            "hole_ref": 1,
            "zones": [{"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"}],
            "green_y_top": 180, "green_y_bottom": 200,
        }]
        svg = render_svg(layout, {"zones_by_hole": zones, "hidden_layers": ["ruler"]})
        assert 'class="layer-ruler"' not in svg

    def test_scoring_arcs_removed(self):
        layout = self._make_layout()
        zones = [{
            "hole_ref": 1,
            "zones": [
                {"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"},
            ],
            "green_y_top": 180, "green_y_bottom": 200,
        }]
        svg = render_svg(layout, {"zones_by_hole": zones})
        assert 'class="layer-scoring_arcs"' not in svg

    def test_scoring_preview_mode(self):
        layout = self._make_layout()
        layout["draw_area"] = {"left": 60, "right": 870, "top": 30, "bottom": 670}
        zones = [{
            "hole_ref": 1,
            "zones": [
                {"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"},
                {"score": -1, "y_top": 180, "y_bottom": 200, "label": "-1", "position": "green"},
            ],
            "green_y_top": 180, "green_y_bottom": 200,
        }]
        svg = render_svg(layout, {"zones_by_hole": zones, "scoring_preview": True})
        assert 'class="layer-scoring_preview"' in svg


class TestVinylPreviewMode:
    def _make_layout(self):
        return {
            "holes": [
                {
                    "ref": 1,
                    "par": 4,
                    "start_x": 200,
                    "start_y": 50,
                    "end_x": 300,
                    "end_y": 200,
                    "direction": 1,
                    "features": [
                        {"category": "fairway", "coords": [[200, 80], [250, 150], [300, 180]]},
                        {"category": "green", "coords": [[280, 190], [300, 200], [310, 195]]},
                        {"category": "tee", "coords": [[190, 50], [210, 55]]},
                        {"category": "bunker", "coords": [[260, 170], [270, 175], [265, 180]]},
                    ],
                },
            ],
            "canvas_width": 900,
            "canvas_height": 700,
            "draw_area": {"left": 60, "right": 870, "top": 30, "bottom": 670},
        }

    def _make_zones(self):
        return [{
            "hole_ref": 1,
            "zones": [
                {"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"},
                {"score": -1, "y_top": 180, "y_bottom": 200, "label": "-1", "position": "green"},
            ],
            "green_y_top": 180,
            "green_y_bottom": 200,
        }]

    def test_dark_background(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        assert "#1a1a1a" in svg  # solid dark background

    def test_green_features_stroke_no_fill(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        # Greens should have green stroke and no fill (or amber fill for interior layer)
        assert 'stroke="#4ade80"' in svg

    def test_white_elements_stroke_only(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        # Fairway rendered as white stroke
        assert 'stroke="#ffffff"' in svg

    def test_bunker_tan_fill(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        assert 'fill="#d2b48c"' in svg

    def test_course_name_vertical_text(self):
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
            "course_name": "Augusta National",
        })
        assert "AUGUSTA NATIONAL" in svg
        assert "rotate(-90)" in svg

    def test_ruler_renders_in_rect_mode(self):
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
        })
        assert 'class="layer-ruler"' in svg
        assert "+5" in svg

    def test_ruler_renders_in_glass_mode(self):
        from app.services.render.glass_template import compute_glass_template, warp_layout
        layout = self._make_layout()
        template = compute_glass_template()
        warped = warp_layout(layout, template)
        svg = render_svg(warped, {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
        })
        assert 'class="layer-ruler"' in svg

    def test_logo_bottom_left(self):
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
            "logo_data_url": "data:image/png;base64,abc123",
        })
        assert "abc123" in svg
        assert "<image" in svg

    def test_green_interior_amber(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        # Green interior amber glow removed (Task 020) — green is stroke-only
        assert 'stroke="#4ade80"' in svg

    def test_terrain_zone_contours_rendered(self):
        terrain_zones = [[
            {"score": 0, "polygon": [[100, 100], [200, 100], [200, 150], [100, 150]],
             "y_center": 125, "y_top": 100, "y_bottom": 150,
             "label_position": {"x": 150, "y": 125, "inside": True}, "leader_line": None},
            {"score": 1, "polygon": [[90, 80], [210, 80], [210, 160], [90, 160]],
             "y_center": 120, "y_top": 80, "y_bottom": 160,
             "label_position": {"x": 150, "y": 120, "inside": True}, "leader_line": None},
        ]]
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
            "terrain_zones": terrain_zones,
        })
        assert 'class="layer-terrain_zones"' in svg
        assert 'stroke="#ffffff"' in svg

    def test_terrain_zone_labels_rendered(self):
        terrain_zones = [[
            {"score": 2, "polygon": [[100, 100], [200, 100], [200, 150], [100, 150]],
             "y_center": 125, "y_top": 100, "y_bottom": 150,
             "label_position": {"x": 150, "y": 125, "inside": True}, "leader_line": None},
        ]]
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
            "terrain_zones": terrain_zones,
        })
        assert "+2" in svg

    def test_terrain_zone_leader_lines(self):
        terrain_zones = [[
            {"score": 1, "polygon": [[100, 100], [101, 100], [100.5, 101]],
             "y_center": 100.3, "y_top": 100, "y_bottom": 101,
             "label_position": {"x": 115, "y": 100.3, "inside": False},
             "leader_line": [[113, 100.3], [101, 100.3]]},
        ]]
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
            "terrain_zones": terrain_zones,
        })
        assert 'stroke-dasharray="1,1"' in svg

    def test_water_rendered_in_blue_fill(self):
        layout = self._make_layout()
        layout["holes"][0]["features"].append(
            {"category": "water", "coords": [[220, 100], [230, 110], [225, 115]]}
        )
        svg = render_svg(layout, {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        assert 'fill="#3b82f6"' in svg

    def test_fairway_rendered_as_filled_green(self):
        layout = self._make_layout()
        svg = render_svg(layout, {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        # Fairway should be solid green fill
        assert 'fill="#4ade80"' in svg

    def test_existing_modes_unchanged(self):
        """Verify standard rect mode output is unaffected by vinyl-preview addition."""
        layout = self._make_layout()
        svg = render_svg(layout)
        assert 'fill="#1a472a"' in svg  # standard background
        assert 'class="layer-fairway"' in svg
        assert "#1a1a1a" not in svg  # no vinyl dark bg in standard mode

    def test_stats_sign_rounded_rect(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        # Stats should render as a rounded rectangle sign
        assert 'rx="2"' in svg
        assert "Par 4" in svg

    def test_hole_numbers_present(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        assert 'class="layer-hole_number"' in svg
        assert ">1</text>" in svg

    def test_dashed_lines_to_tee(self):
        svg = render_svg(self._make_layout(), {"vinyl_preview": True, "zones_by_hole": self._make_zones()})
        assert 'class="layer-hole_tee_lines"' in svg
        assert 'stroke-dasharray="2,2"' in svg

    def test_qr_code_in_vinyl_preview(self):
        svg = render_svg(self._make_layout(), {
            "vinyl_preview": True,
            "zones_by_hole": self._make_zones(),
            "qr_svg": "<svg>QR</svg>",
        })
        assert "QR code embedded" in svg


import re


class TestRulerReadability:
    def _make_layout(self):
        return {
            "holes": [
                {
                    "ref": 1, "par": 4,
                    "start_x": 200, "start_y": 50, "end_x": 300, "end_y": 200,
                    "direction": 1,
                    "features": [
                        {"category": "fairway", "coords": [[200, 80], [250, 150], [300, 180]]},
                        {"category": "green", "coords": [[280, 190], [300, 200], [310, 195]]},
                        {"category": "tee", "coords": [[190, 50], [210, 55]]},
                    ],
                },
            ],
            "canvas_width": 900,
            "canvas_height": 700,
            "draw_area": {"left": 60, "right": 870, "top": 30, "bottom": 670},
        }

    def _make_full_zones(self):
        """Zones with all score levels including below-green."""
        return [{
            "hole_ref": 1,
            "zones": [
                {"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"},
                {"score": 4, "y_top": 60, "y_bottom": 85, "label": "+4", "position": "above"},
                {"score": 3, "y_top": 85, "y_bottom": 107, "label": "+3", "position": "above"},
                {"score": 2, "y_top": 107, "y_bottom": 127, "label": "+2", "position": "above"},
                {"score": 1, "y_top": 127, "y_bottom": 145, "label": "+1", "position": "above"},
                {"score": 0, "y_top": 145, "y_bottom": 160, "label": "0", "position": "above"},
                {"score": -1, "y_top": 160, "y_bottom": 180, "label": "-1", "position": "green"},
                {"score": 1, "y_top": 180, "y_bottom": 195, "label": "+1", "position": "below"},
                {"score": 2, "y_top": 195, "y_bottom": 210, "label": "+2", "position": "below"},
            ],
            "green_y_top": 160,
            "green_y_bottom": 180,
        }]

    def test_score_labels_min_font_size(self):
        """Score labels should have font-size >= 8."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        # Extract font-size values from ruler text elements
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        font_sizes = re.findall(r'font-size="(\d+)"', ruler_svg)
        for size in font_sizes:
            assert int(size) >= 8, f"Font size {size} is below minimum 8pt"

    def test_score_labels_in_rectangles(self):
        """Score labels should be in alternating filled/outline rectangles."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        # Should have both white-filled rects (odd scores) and outline rects (even scores)
        assert 'fill="white"' in ruler_svg, "Should have white-filled score rects"
        assert 'fill="none" stroke="white"' in ruler_svg, "Should have outline score rects"
        # Score labels should be centered in rectangles
        assert 'text-anchor="middle"' in ruler_svg

    def test_hole_number_at_top_of_section(self):
        """Hole number rect should be at top of section, separate from score rects."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        # Hole number should appear before score labels
        hole_pos = ruler_svg.find(">1</text>")
        score_pos = ruler_svg.find(">+5</text>")
        assert hole_pos < score_pos, "Hole number should come before scores"

    def test_hole_number_badge(self):
        """Hole number should be in a rect at top of section."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        assert ">1</text>" in ruler_svg, "Hole number should be in badge"
        # No rx attributes (sharp corners)
        assert 'rx=' not in ruler_svg

    def test_no_combined_labels_zones_premerged(self):
        """Zones are pre-merged in scoring.py — no combined labels needed in ruler."""
        layout = self._make_layout()
        # Pre-merged: only one below-green zone (scoring.py merges small ones)
        zones = [{
            "hole_ref": 1,
            "zones": [
                {"score": 5, "y_top": 30, "y_bottom": 60, "label": "+5", "position": "above"},
                {"score": -1, "y_top": 160, "y_bottom": 180, "label": "-1", "position": "green"},
                {"score": 2, "y_top": 180, "y_bottom": 188, "label": "+2", "position": "below"},
            ],
            "green_y_top": 160,
            "green_y_bottom": 180,
        }]
        svg = render_svg(layout, {"zones_by_hole": zones})
        # Should have +2 label, no combined "+1/+2"
        assert "+2" in svg
        assert "+1/+2" not in svg

    def test_alternating_score_rect_styles(self):
        """Score rects should alternate between filled and outline styles."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        # Odd scores get white fill, even scores get outline
        assert 'fill="white" stroke="none" opacity="0.8"' in ruler_svg
        assert 'fill="none" stroke="white"' in ruler_svg

    def test_ruler_rect_mode(self):
        """Ruler should render in rect mode."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        assert 'class="layer-ruler"' in svg

    def test_ruler_glass_mode(self):
        """Ruler should render in glass/warped mode."""
        from app.services.render.glass_template import compute_glass_template, warp_layout
        layout = self._make_layout()
        template = compute_glass_template()
        warped = warp_layout(layout, template)
        svg = render_svg(warped, {
            "vinyl_preview": True,
            "zones_by_hole": self._make_full_zones(),
        })
        assert 'class="layer-ruler"' in svg
        # Should have hole number and score labels
        assert 'fill="white"' in svg

    def test_score_rects_in_separate_column(self):
        """Score rectangles should be in a separate column with sharp corners."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        # Score rects present (width=16 for score column)
        assert 'width="16.0"' in ruler_svg, "Score rects should be 16px wide"
        # Hole number column present (width=14)
        assert 'width="14.0"' in ruler_svg, "Hole number rects should be 14px wide"
        # No rx attributes (sharp corners)
        assert 'rx=' not in ruler_svg

    def test_hole_number_alternating_fill(self):
        """Odd holes should have white fill, even holes should have outline only."""
        layout = self._make_layout()
        # Test with hole ref 1 (odd) — should be white filled
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        # Odd hole (1): white filled rect with dark knocked-out text
        assert 'fill="white"' in ruler_svg and 'fill="#1a1a1a"' in ruler_svg

    def test_ruler_two_column_layout(self):
        """Ruler should have two columns: hole numbers + scores, with tick lines."""
        layout = self._make_layout()
        svg = render_svg(layout, {"zones_by_hole": self._make_full_zones()})
        ruler_match = re.search(r'<g class="layer-ruler">(.*?)</g>', svg, re.DOTALL)
        assert ruler_match
        ruler_svg = ruler_match.group(1)
        # Multiple rects present (hole number full-height + score rects)
        rect_count = ruler_svg.count('<rect')
        assert rect_count >= 5, f"Expected many rects, got {rect_count}"
        # Hole number text should be rotated 90°
        assert 'rotate(-90' in ruler_svg, "Hole numbers should be rotated 90°"
        # Tick lines at zone boundaries
        assert '<line' in ruler_svg, "Tick marks at zone boundaries"
