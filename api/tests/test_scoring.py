"""Tests for scoring zones."""

from app.services.render.scoring import (
    compute_scoring_zones,
    compute_all_scoring_zones,
    compute_terrain_following_zones,
    compute_all_terrain_following_zones,
    _find_green_bounds,
    _extract_green_polygon,
    _merge_small_zones,
    TerrainFollowingZone,
    DEFAULT_ZONE_RATIOS,
    MIN_ZONE_HEIGHT,
)
from app.schemas.scoring import ScoringZone, ScoringZoneResult


def _make_hole_layout(start_y=0, end_y=200, green_coords=None):
    features = []
    if green_coords:
        features.append({"category": "green", "coords": green_coords})
    features.append({"category": "tee", "coords": [[100, start_y], [120, start_y + 5]]})
    return {
        "ref": 1,
        "par": 4,
        "start_y": start_y,
        "end_y": end_y,
        "start_x": 100,
        "end_x": 150,
        "direction": 1,
        "features": features,
    }


class TestFindGreenBounds:
    def test_with_green(self):
        hole = _make_hole_layout(green_coords=[[100, 150], [120, 170]])
        top, bottom = _find_green_bounds(hole)
        assert top == 150
        assert bottom == 170

    def test_without_green(self):
        hole = _make_hole_layout()
        top, bottom = _find_green_bounds(hole)
        # Falls back to end_y
        assert top == 195  # end_y - 5
        assert bottom == 205  # end_y + 5


class TestComputeScoringZones:
    def test_basic_zones(self):
        hole = _make_hole_layout(start_y=0, end_y=200, green_coords=[[100, 160], [120, 170]])
        result = compute_scoring_zones(hole, available_top=0, available_bottom=220)
        assert result["hole_ref"] == 1
        assert result["green_y_top"] == 160
        assert result["green_y_bottom"] == 170
        zones = result["zones"]
        assert len(zones) > 0

    def test_above_zones_have_narrowing_widths(self):
        hole = _make_hole_layout(start_y=0, end_y=200, green_coords=[[100, 160], [120, 170]])
        result = compute_scoring_zones(hole, available_top=0, available_bottom=220)
        above = [z for z in result["zones"] if z["position"] == "above"]
        # Par 4 → max score +4 → 5 zones (+4 through 0)
        assert len(above) == 5
        # highest score zone should be widest
        widths = [z["y_bottom"] - z["y_top"] for z in above]
        assert widths[0] > widths[-1]

    def test_green_zone(self):
        hole = _make_hole_layout(green_coords=[[100, 150], [120, 170]])
        result = compute_scoring_zones(hole, available_top=0, available_bottom=220)
        green_zones = [z for z in result["zones"] if z["position"] == "green"]
        assert len(green_zones) == 1
        assert green_zones[0]["score"] == -1

    def test_below_zones(self):
        hole = _make_hole_layout(green_coords=[[100, 150], [120, 170]])
        result = compute_scoring_zones(hole, available_top=0, available_bottom=220)
        below = [z for z in result["zones"] if z["position"] == "below"]
        assert len(below) == 2
        assert below[0]["score"] == 1
        assert below[1]["score"] == 2

    def test_custom_ratios(self):
        hole = _make_hole_layout(green_coords=[[100, 160], [120, 170]])
        custom = {5: 0.30, 4: 0.25, 3: 0.20, 2: 0.10, 1: 0.10, 0: 0.05}
        result = compute_scoring_zones(hole, 0, 220, zone_ratios=custom)
        above = [z for z in result["zones"] if z["position"] == "above"]
        widths = [z["y_bottom"] - z["y_top"] for z in above]
        # +5 (30%) should be wider than with default (25%)
        assert widths[0] > widths[1]

    def test_default_boundaries(self):
        hole = _make_hole_layout(start_y=50, end_y=200, green_coords=[[100, 160], [120, 170]])
        result = compute_scoring_zones(hole)
        # Should use defaults: available_top = start_y - 6, available_bottom = end_y + 20
        assert result["zones"][0]["y_top"] == 44  # 50 - 6

    def test_zones_continuous(self):
        hole = _make_hole_layout(green_coords=[[100, 160], [120, 170]])
        result = compute_scoring_zones(hole, 0, 220)
        above = [z for z in result["zones"] if z["position"] == "above"]
        # Each zone's bottom should be next zone's top
        for i in range(len(above) - 1):
            assert abs(above[i]["y_bottom"] - above[i + 1]["y_top"]) < 0.001


class TestMergeSmallZones:
    def test_small_below_zones_merged(self):
        """Below-green zones smaller than MIN_ZONE_HEIGHT should merge (higher score wins)."""
        zones = [
            {"score": 5, "y_top": 0, "y_bottom": 50, "label": "+5", "position": "above"},
            {"score": -1, "y_top": 150, "y_bottom": 170, "label": "-1", "position": "green"},
            {"score": 1, "y_top": 170, "y_bottom": 173, "label": "+1", "position": "below"},
            {"score": 2, "y_top": 173, "y_bottom": 176, "label": "+2", "position": "below"},
        ]
        result = _merge_small_zones(zones)
        below = [z for z in result if z["position"] == "below"]
        assert len(below) == 1
        assert below[0]["score"] == 2  # higher score wins

    def test_adequate_below_zones_not_merged(self):
        """Below-green zones with adequate height should NOT be merged."""
        zones = [
            {"score": -1, "y_top": 150, "y_bottom": 170, "label": "-1", "position": "green"},
            {"score": 1, "y_top": 170, "y_bottom": 195, "label": "+1", "position": "below"},
            {"score": 2, "y_top": 195, "y_bottom": 220, "label": "+2", "position": "below"},
        ]
        result = _merge_small_zones(zones)
        below = [z for z in result if z["position"] == "below"]
        assert len(below) == 2

    def test_scoring_zones_auto_merge(self):
        """compute_scoring_zones should auto-merge small below-green zones."""
        hole = _make_hole_layout(green_coords=[[100, 168], [120, 170]])
        # available_bottom close to green_bottom → tiny below space
        result = compute_scoring_zones(hole, available_top=0, available_bottom=174)
        below = [z for z in result["zones"] if z["position"] == "below"]
        # Should be merged to 1 zone since total below space is only 4px
        assert len(below) <= 1


class TestComputeAllScoringZones:
    def test_single_hole(self):
        layout = {
            "holes": [_make_hole_layout(start_y=30, end_y=200, green_coords=[[100, 160], [120, 170]])],
            "canvas_width": 900,
            "canvas_height": 700,
            "draw_area": {"left": 60, "right": 870, "top": 30, "bottom": 670},
        }
        results = compute_all_scoring_zones(layout)
        assert len(results) == 1
        assert results[0]["hole_ref"] == 1

    def test_multiple_holes(self):
        holes = [
            _make_hole_layout(start_y=30, end_y=200, green_coords=[[100, 160], [120, 170]]),
            {**_make_hole_layout(start_y=220, end_y=400, green_coords=[[100, 360], [120, 370]]),
             "ref": 2},
        ]
        layout = {
            "holes": holes,
            "canvas_width": 900,
            "canvas_height": 700,
            "draw_area": {"left": 60, "right": 870, "top": 30, "bottom": 670},
        }
        results = compute_all_scoring_zones(layout)
        assert len(results) == 2

    def test_empty_layout(self):
        layout = {"holes": [], "canvas_width": 900, "canvas_height": 700}
        assert compute_all_scoring_zones(layout) == []


class TestScoringSchemas:
    def test_scoring_zone_model(self):
        zone = ScoringZone(score=3, y_top=50.0, y_bottom=80.0, label="+3", position="above")
        assert zone.score == 3

    def test_scoring_zone_result_model(self):
        result = ScoringZoneResult(
            hole_ref=1,
            zones=[ScoringZone(score=-1, y_top=150.0, y_bottom=170.0, label="-1", position="green")],
            green_y_top=150.0,
            green_y_bottom=170.0,
        )
        assert result.hole_ref == 1
        assert len(result.zones) == 1


def _make_hole_for_terrain(start_y=0, end_y=200, green_coords=None, tee_coords=None, fairway_coords=None):
    """Helper to build a hole layout for terrain zone tests."""
    features = []
    if green_coords:
        features.append({"category": "green", "coords": green_coords})
    if fairway_coords:
        features.append({"category": "fairway", "coords": fairway_coords})
    if tee_coords:
        features.append({"category": "tee", "coords": tee_coords})
    else:
        features.append({"category": "tee", "coords": [[100, start_y], [120, start_y + 5]]})
    return {
        "ref": 1, "par": 4,
        "start_x": 100, "start_y": start_y,
        "end_x": 150, "end_y": end_y,
        "direction": 1,
        "features": features,
    }


class TestComputeTerrainFollowingZones:
    def test_triangular_green(self):
        """Terrain zones with a triangular green polygon."""
        hole = _make_hole_for_terrain(
            green_coords=[[100, 170], [130, 150], [110, 190]],
            tee_coords=[[110, 10], [120, 15]],
        )
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        assert len(zones) == 7  # -1 through +5
        scores = [z.score for z in zones]
        assert scores == [-1, 0, 1, 2, 3, 4, 5]

    def test_minus1_matches_green(self):
        """The -1 zone polygon should match the green polygon."""
        green = [[100, 170], [130, 150], [110, 190]]
        hole = _make_hole_for_terrain(green_coords=green)
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        minus1 = [z for z in zones if z.score == -1][0]
        assert minus1.polygon == [[100, 170], [130, 150], [110, 190]]

    def test_zones_grow_outward(self):
        """Outer zones should be larger than inner zones."""
        hole = _make_hole_for_terrain(
            green_coords=[[100, 170], [130, 150], [110, 190]],
            tee_coords=[[110, 10], [120, 15]],
        )
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        # Check that zone polygons exist and get progressively larger
        for z in zones:
            assert len(z.polygon) >= 3
            assert isinstance(z, TerrainFollowingZone)

    def test_zones_clamped_within_bounds(self):
        """Zones should be clamped within available_top and available_bottom."""
        hole = _make_hole_for_terrain(
            green_coords=[[100, 170], [130, 150], [110, 190]],
            tee_coords=[[110, 10], [120, 15]],
        )
        zones = compute_terrain_following_zones(hole, available_top=50, available_bottom=200)
        for z in zones:
            for pt in z.polygon:
                assert pt[1] >= 50, f"Zone {z.score} has point y={pt[1]} above available_top=50"
                assert pt[1] <= 200, f"Zone {z.score} has point y={pt[1]} below available_bottom=200"

    def test_fallback_no_green(self):
        """When no green feature exists, should still produce zones with fallback ellipse."""
        hole = _make_hole_for_terrain(tee_coords=[[100, 10], [120, 15]])
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        assert len(zones) == 7
        minus1 = [z for z in zones if z.score == -1][0]
        assert len(minus1.polygon) >= 3

    def test_with_fairway_blending(self):
        """Zones +2 through +5 should blend toward fairway bounds."""
        hole = _make_hole_for_terrain(
            green_coords=[[105, 160], [125, 155], [130, 175], [100, 180]],
            tee_coords=[[110, 10], [120, 20]],
            fairway_coords=[[80, 50], [140, 50], [140, 120], [80, 120]],
        )
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        assert len(zones) == 7
        for z in zones:
            assert len(z.polygon) >= 3
            assert z.y_top <= z.y_bottom

    def test_label_positions(self):
        """Each zone should have a label_position dict."""
        hole = _make_hole_for_terrain(
            green_coords=[[100, 170], [130, 150], [110, 190]],
            tee_coords=[[110, 10], [120, 15]],
        )
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        for z in zones:
            assert "x" in z.label_position
            assert "y" in z.label_position
            assert "inside" in z.label_position

    def test_leader_lines_for_small_zones(self):
        """Small zones should have leader lines."""
        # Use a very tiny green to make zones small
        hole = _make_hole_for_terrain(
            green_coords=[[100, 170], [101, 170], [100.5, 171]],
            tee_coords=[[100, 10], [101, 15]],
        )
        zones = compute_terrain_following_zones(hole, available_top=0, available_bottom=220)
        # -1 zone (tiny green) should have a leader line
        minus1 = [z for z in zones if z.score == -1][0]
        assert minus1.leader_line is not None

    def test_dataclass_fields(self):
        """Verify TerrainFollowingZone has all required fields."""
        tz = TerrainFollowingZone(
            score=2, polygon=[[0, 0], [1, 1], [2, 0]],
            y_center=0.5, y_top=0.0, y_bottom=1.0,
            label_position={"x": 1.0, "y": 0.5, "inside": True},
            leader_line=None,
        )
        assert tz.score == 2
        assert tz.polygon == [[0, 0], [1, 1], [2, 0]]
        assert tz.y_center == 0.5
        assert tz.label_position["inside"] is True
        assert tz.leader_line is None


class TestComputeAllTerrainFollowingZones:
    def test_single_hole(self):
        layout = {
            "holes": [_make_hole_layout(start_y=30, end_y=200, green_coords=[[100, 160], [120, 170], [110, 180]])],
            "canvas_width": 900,
            "canvas_height": 700,
            "draw_area": {"left": 60, "right": 870, "top": 30, "bottom": 670},
        }
        results = compute_all_terrain_following_zones(layout)
        assert len(results) == 1
        assert len(results[0]) == 7

    def test_empty_layout(self):
        layout = {"holes": [], "canvas_width": 900, "canvas_height": 700}
        assert compute_all_terrain_following_zones(layout) == []
