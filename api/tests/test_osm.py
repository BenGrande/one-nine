"""Tests for OSM service."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.golf.osm import parse_overpass_features, _determine_category, fetch_course_map


class TestDetermineCategory:
    def test_fairway(self):
        assert _determine_category({"golf": "fairway"}) == "fairway"

    def test_green(self):
        assert _determine_category({"golf": "green"}) == "green"

    def test_tee(self):
        assert _determine_category({"golf": "tee"}) == "tee"

    def test_bunker(self):
        assert _determine_category({"golf": "bunker"}) == "bunker"

    def test_rough(self):
        assert _determine_category({"golf": "rough"}) == "rough"

    def test_hole(self):
        assert _determine_category({"golf": "hole"}) == "hole"

    def test_cartpath(self):
        assert _determine_category({"golf": "cartpath"}) == "path"

    def test_path(self):
        assert _determine_category({"golf": "path"}) == "path"

    def test_driving_range(self):
        assert _determine_category({"golf": "driving_range"}) == "fairway"

    def test_water_natural(self):
        assert _determine_category({"natural": "water"}) == "water"

    def test_water_tag(self):
        assert _determine_category({"water": "lake"}) == "water"

    def test_golf_course(self):
        assert _determine_category({"leisure": "golf_course"}) == "course_boundary"

    def test_unknown(self):
        assert _determine_category({"amenity": "parking"}) is None


class TestParseOverpassFeatures:
    def test_empty(self):
        assert parse_overpass_features({"elements": []}) == []

    def test_parses_way_with_nodes(self):
        raw = {
            "elements": [
                {"type": "node", "id": 1, "lat": 36.0, "lon": -121.0},
                {"type": "node", "id": 2, "lat": 36.001, "lon": -121.001},
                {
                    "type": "way",
                    "id": 100,
                    "tags": {"golf": "fairway"},
                    "nodes": [1, 2],
                },
            ]
        }
        features = parse_overpass_features(raw)
        assert len(features) == 1
        assert features[0]["category"] == "fairway"
        assert features[0]["id"] == "100"
        assert len(features[0]["coords"]) == 2

    def test_skips_way_without_tags(self):
        raw = {
            "elements": [
                {"type": "node", "id": 1, "lat": 36.0, "lon": -121.0},
                {"type": "node", "id": 2, "lat": 36.001, "lon": -121.001},
                {"type": "way", "id": 100, "nodes": [1, 2]},
            ]
        }
        assert parse_overpass_features(raw) == []

    def test_skips_way_with_less_than_2_coords(self):
        raw = {
            "elements": [
                {"type": "node", "id": 1, "lat": 36.0, "lon": -121.0},
                {
                    "type": "way",
                    "id": 100,
                    "tags": {"golf": "fairway"},
                    "nodes": [1],
                },
            ]
        }
        assert parse_overpass_features(raw) == []

    def test_extracts_ref_par_name(self):
        raw = {
            "elements": [
                {"type": "node", "id": 1, "lat": 36.0, "lon": -121.0},
                {"type": "node", "id": 2, "lat": 36.001, "lon": -121.001},
                {
                    "type": "way",
                    "id": 100,
                    "tags": {"golf": "hole", "ref": "5", "par": "4", "name": "Hole 5"},
                    "nodes": [1, 2],
                },
            ]
        }
        features = parse_overpass_features(raw)
        assert features[0]["ref"] == "5"
        assert features[0]["par"] == 4
        assert features[0]["name"] == "Hole 5"

    def test_skips_unknown_category(self):
        raw = {
            "elements": [
                {"type": "node", "id": 1, "lat": 36.0, "lon": -121.0},
                {"type": "node", "id": 2, "lat": 36.001, "lon": -121.001},
                {
                    "type": "way",
                    "id": 100,
                    "tags": {"amenity": "parking"},
                    "nodes": [1, 2],
                },
            ]
        }
        assert parse_overpass_features(raw) == []


class TestFetchCourseMap:
    @pytest.mark.asyncio
    async def test_overpass_returns_none(self):
        with patch("app.services.golf.osm.query_overpass", return_value=None):
            result = await fetch_course_map(36.0, -121.0)

        assert result == {"features": [], "center": [36.0, -121.0]}

    @pytest.mark.asyncio
    async def test_radius_capped_at_3000(self):
        with patch("app.services.golf.osm.query_overpass", return_value={"elements": []}) as mock_qo:
            await fetch_course_map(36.0, -121.0, 5000)

        # Verify the query uses 3000 (capped), not 5000
        call_args = mock_qo.call_args[0][0]
        assert "around:3000" in call_args
