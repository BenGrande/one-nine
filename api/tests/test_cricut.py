"""Tests for Cricut 3-color SVG export."""

from app.services.render.cricut import (
    render_cricut_white,
    render_cricut_green,
    render_cricut_tan,
    render_cricut_guide,
    _compact_arrange,
    _extract_features_by_category,
    _bbox,
    _scale_ruler_element,
)
from app.services.render.glass_template import compute_glass_template, warp_layout
from app.services.render.layout import compute_layout


def _make_layout():
    """Create a test layout with features of various categories."""
    return {
        "holes": [
            {
                "ref": 1,
                "par": 4,
                "yardage": 400,
                "handicap": 5,
                "start_x": 200,
                "start_y": 50,
                "end_x": 300,
                "end_y": 200,
                "direction": 1,
                "features": [
                    {"id": "f1", "category": "fairway", "coords": [[200, 80], [250, 150], [300, 180]]},
                    {"id": "g1", "category": "green", "coords": [[280, 190], [300, 200], [310, 195]]},
                    {"id": "t1", "category": "tee", "coords": [[190, 50], [210, 55], [205, 60]]},
                    {"id": "b1", "category": "bunker", "coords": [[260, 170], [270, 175], [265, 180]]},
                ],
            },
            {
                "ref": 2,
                "par": 3,
                "yardage": 180,
                "handicap": 15,
                "start_x": 300,
                "start_y": 220,
                "end_x": 200,
                "end_y": 350,
                "direction": -1,
                "features": [
                    {"id": "f2", "category": "fairway", "coords": [[300, 240], [250, 300], [200, 330]]},
                    {"id": "g2", "category": "green", "coords": [[190, 340], [210, 350], [205, 355]]},
                    {"id": "b2", "category": "bunker", "coords": [[220, 310], [230, 315], [225, 320]]},
                ],
            },
        ],
        "canvas_width": 900,
        "canvas_height": 700,
        "draw_area": {"left": 60, "right": 870, "top": 30, "bottom": 670},
    }


class TestBbox:
    def test_basic(self):
        bb = _bbox([[0, 0], [10, 20]])
        assert bb["min_x"] == 0
        assert bb["max_x"] == 10
        assert bb["width"] == 10
        assert bb["height"] == 20


class TestExtractFeatures:
    def test_extract_greens_and_tees(self):
        layout = _make_layout()
        pieces = _extract_features_by_category(layout, {"green", "tee"})
        assert len(pieces) == 3  # 2 greens + 1 tee
        categories = {p["category"] for p in pieces}
        assert categories == {"green", "tee"}

    def test_extract_bunkers(self):
        layout = _make_layout()
        pieces = _extract_features_by_category(layout, {"bunker"})
        assert len(pieces) == 2

    def test_empty_layout(self):
        pieces = _extract_features_by_category({"holes": []}, {"green"})
        assert pieces == []

    def test_preserves_hole_ref(self):
        layout = _make_layout()
        pieces = _extract_features_by_category(layout, {"bunker"})
        refs = {p["hole_ref"] for p in pieces}
        assert refs == {1, 2}


class TestCompactArrange:
    def test_arranges_pieces(self):
        pieces = [
            {"hole_ref": 1, "category": "green", "coords": [[0, 0], [10, 0], [10, 10], [0, 10]], "id": "g1"},
            {"hole_ref": 2, "category": "green", "coords": [[0, 0], [15, 0], [15, 8], [0, 8]], "id": "g2"},
        ]
        arranged = _compact_arrange(pieces, canvas_width=100, padding=5)
        assert len(arranged) == 2
        # All pieces should have placed coordinates
        for p in arranged:
            assert "placed_coords" in p
            assert "placed_x" in p
            assert "placed_y" in p

    def test_wraps_rows(self):
        # Create pieces that won't fit in one row
        pieces = [
            {"hole_ref": i, "category": "green",
             "coords": [[0, 0], [40, 0], [40, 20], [0, 20]], "id": f"g{i}"}
            for i in range(5)
        ]
        arranged = _compact_arrange(pieces, canvas_width=100, padding=5)
        # Should wrap to multiple rows
        y_values = {p["placed_y"] for p in arranged}
        assert len(y_values) > 1  # multiple rows

    def test_empty(self):
        assert _compact_arrange([]) == []

    def test_canvas_height_computed(self):
        pieces = [
            {"hole_ref": 1, "category": "green", "coords": [[0, 0], [10, 0], [10, 10], [0, 10]], "id": "g1"},
        ]
        arranged = _compact_arrange(pieces, canvas_width=100)
        assert arranged[0]["canvas_height"] > 0


class TestScaleRuler:
    def test_produces_svg(self):
        result = _scale_ruler_element(50, 100)
        assert "<g" in result
        assert "10mm" in result
        assert "100% scale" in result


class TestRenderCricutWhite:
    def test_basic_render(self):
        layout = _make_layout()
        zones = [{"hole_ref": 1, "zones": [], "green_y_top": 190, "green_y_bottom": 200}]
        svg = render_cricut_white(layout, zones)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        # Should have white elements
        assert 'fill="none"' in svg
        assert '#ffffff' in svg  # white elements

    def test_includes_hole_numbers(self):
        layout = _make_layout()
        svg = render_cricut_white(layout, [])
        assert ">1</text>" in svg
        assert ">2</text>" in svg

    def test_includes_stats_boxes(self):
        layout = _make_layout()
        svg = render_cricut_white(layout, [])
        assert "Par 4" in svg  # stats box content

    def test_includes_course_name(self):
        layout = _make_layout()
        svg = render_cricut_white(layout, [], opts={"course_name": "Pebble Beach"})
        assert "PEBBLE BEACH" in svg

    def test_warped_mode(self):
        holes = [
            {
                "ref": 1, "par": 4, "yardage": 400, "difficulty": 5.0,
                "handicap": None, "route_coords": [[36.0, -121.0], [36.001, -121.001]],
                "features": [
                    {"id": "1", "category": "fairway", "ref": None, "par": None, "name": None,
                     "coords": [[36.0, -121.0], [36.0005, -121.0005]]},
                ],
            }
        ]
        layout = compute_layout(holes)
        template = compute_glass_template()
        warped = warp_layout(layout, template)
        svg = render_cricut_white(warped, [], template)
        assert svg.startswith("<svg")
        assert "glassClip" in svg  # warped mode uses glass clipping

    def test_includes_hole_stats(self):
        layout = _make_layout()
        svg = render_cricut_white(layout, [])
        assert "Par 4" in svg
        assert "400 yd" in svg


class TestRenderCricutGreen:
    def test_basic_render(self):
        layout = _make_layout()
        svg = render_cricut_green(layout)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert '#4ade80' in svg  # green color

    def test_includes_green_features(self):
        layout = _make_layout()
        svg = render_cricut_green(layout)
        assert '#4ade80' in svg  # green elements present

    def test_no_white_elements(self):
        layout = _make_layout()
        svg = render_cricut_green(layout)
        assert 'layer-hole_number' not in svg  # no white elements

    def test_empty_features(self):
        layout = {"holes": [{"ref": 1, "features": [], "start_x": 100, "start_y": 50, "end_x": 150, "end_y": 200, "direction": 1}], "canvas_width": 900, "canvas_height": 700}
        svg = render_cricut_green(layout)
        assert svg.startswith("<svg")


class TestRenderCricutTan:
    def test_basic_render(self):
        layout = _make_layout()
        svg = render_cricut_tan(layout)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_has_bunker_fills(self):
        layout = _make_layout()
        svg = render_cricut_tan(layout)
        assert "#d2b48c" in svg  # tan color

    def test_no_white_elements(self):
        layout = _make_layout()
        svg = render_cricut_tan(layout)
        assert 'layer-hole_number' not in svg

    def test_empty_bunkers(self):
        layout = {"holes": [{"ref": 1, "features": [], "start_x": 100, "start_y": 50, "end_x": 150, "end_y": 200, "direction": 1}], "canvas_width": 900, "canvas_height": 700}
        svg = render_cricut_tan(layout)
        assert svg.startswith("<svg")


class TestRenderCricutGuide:
    def test_basic_render(self):
        layout = _make_layout()
        svg = render_cricut_guide(layout)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_has_piece_labels(self):
        layout = _make_layout()
        svg = render_cricut_guide(layout)
        assert "G1" in svg
        assert "B1" in svg
        assert "T1" in svg

    def test_warped_guide(self):
        holes = [
            {
                "ref": 1, "par": 4, "yardage": 400, "difficulty": 5.0,
                "handicap": None, "route_coords": [[36.0, -121.0], [36.001, -121.001]],
                "features": [
                    {"id": "1", "category": "green", "ref": None, "par": None, "name": None,
                     "coords": [[36.001, -121.001], [36.0011, -121.0011]]},
                ],
            }
        ]
        layout = compute_layout(holes)
        template = compute_glass_template()
        warped = warp_layout(layout, template)
        svg = render_cricut_guide(warped)
        assert svg.startswith("<svg")
        assert "glassClip" not in svg  # guide doesn't clip
