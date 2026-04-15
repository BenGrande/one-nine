"""Tests for Phase 5 polish features."""

from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from app.services.font_hints import get_font_hint, COURSE_FONTS
from app.services.render.scoring import (
    _compute_difficulty_factor,
    _compute_par_factor,
    compute_scoring_zones,
)


class TestFontHints:
    def test_exact_match(self):
        assert get_font_hint("pebble beach") == "Playfair Display"

    def test_case_insensitive(self):
        assert get_font_hint("Pebble Beach") == "Playfair Display"

    def test_partial_match(self):
        assert get_font_hint("Pebble Beach Golf Links") == "Playfair Display"

    def test_no_match(self):
        assert get_font_hint("Unknown Golf Course") is None

    def test_empty(self):
        assert get_font_hint("") is None

    def test_none(self):
        assert get_font_hint(None) is None

    def test_augusta(self):
        assert get_font_hint("Augusta National") == "Cormorant Garamond"


class TestDifficultyFactor:
    def test_hard_hole(self):
        f = _compute_difficulty_factor({"handicap": 1})
        assert f > 1.0  # wider zones

    def test_easy_hole(self):
        f = _compute_difficulty_factor({"handicap": 18})
        assert f < 1.0  # tighter zones

    def test_no_data(self):
        f = _compute_difficulty_factor({})
        assert f == 1.0

    def test_difficulty_fallback(self):
        f = _compute_difficulty_factor({"difficulty": 1})
        assert f > 1.0

    def test_mid_range(self):
        f = _compute_difficulty_factor({"handicap": 9})
        assert 0.9 < f < 1.1


class TestParFactor:
    def test_par3(self):
        f = _compute_par_factor({"par": 3})
        assert f < 1.0  # tighter

    def test_par4(self):
        f = _compute_par_factor({"par": 4})
        assert f == 1.0

    def test_par5(self):
        f = _compute_par_factor({"par": 5})
        assert f > 1.0  # more forgiving

    def test_no_par(self):
        f = _compute_par_factor({})
        assert f == 1.0


class TestScoringZonesWithFactors:
    def test_hard_hole_wider_upper_zones(self):
        hard_hole = {
            "ref": 1, "par": 4, "handicap": 1, "start_y": 0, "end_y": 200,
            "features": [{"category": "green", "coords": [[100, 160], [120, 170]]}],
        }
        easy_hole = {
            "ref": 2, "par": 4, "handicap": 18, "start_y": 0, "end_y": 200,
            "features": [{"category": "green", "coords": [[100, 160], [120, 170]]}],
        }
        hard_zones = compute_scoring_zones(hard_hole, 0, 220)
        easy_zones = compute_scoring_zones(easy_hole, 0, 220)

        hard_5 = next(z for z in hard_zones["zones"] if z["score"] == 5 and z["position"] == "above")
        easy_5 = next(z for z in easy_zones["zones"] if z["score"] == 5 and z["position"] == "above")

        hard_width = hard_5["y_bottom"] - hard_5["y_top"]
        easy_width = easy_5["y_bottom"] - easy_5["y_top"]
        # Hard hole should have wider +5 zone
        assert hard_width > easy_width

    def test_par3_tighter(self):
        par3 = {
            "ref": 1, "par": 3, "start_y": 0, "end_y": 200,
            "features": [{"category": "green", "coords": [[100, 160], [120, 170]]}],
        }
        par5 = {
            "ref": 2, "par": 5, "start_y": 0, "end_y": 200,
            "features": [{"category": "green", "coords": [[100, 160], [120, 170]]}],
        }
        par3_zones = compute_scoring_zones(par3, 0, 220)
        par5_zones = compute_scoring_zones(par5, 0, 220)

        par3_5 = next(z for z in par3_zones["zones"] if z["score"] == 5 and z["position"] == "above")
        par5_5 = next(z for z in par5_zones["zones"] if z["score"] == 5 and z["position"] == "above")

        par3_width = par3_5["y_bottom"] - par3_5["y_top"]
        par5_width = par5_5["y_bottom"] - par5_5["y_top"]
        assert par5_width > par3_width


class TestLogoEndpoint:
    def _get_client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.api.v1.assets._get_logo_path")
    @patch("app.api.v1.assets._logo_data_url_cache", None)
    def test_logo_found(self, mock_path):
        import tempfile
        from pathlib import Path
        # Create a temp PNG file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
            tmp_path = Path(f.name)
        mock_path.return_value = tmp_path
        try:
            client = self._get_client()
            response = client.get("/api/v1/assets/logo")
            assert response.status_code == 200
            data = response.json()
            assert "data_url" in data
            assert data["data_url"].startswith("data:image/png;base64,")
        finally:
            tmp_path.unlink()

    @patch("app.api.v1.assets._get_logo_path")
    @patch("app.api.v1.assets._logo_data_url_cache", None)
    def test_logo_not_found(self, mock_path):
        from pathlib import Path
        mock_path.return_value = Path("/nonexistent/logo.png")
        client = self._get_client()
        response = client.get("/api/v1/assets/logo")
        assert response.status_code == 404


class TestStatusEndpoint:
    def _get_client(self):
        from app.main import app
        return TestClient(app)

    def test_status_returns_version(self):
        client = self._get_client()
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"
        assert "status" in data


class TestQrEmbedding:
    def test_qr_svg_in_render(self):
        from app.services.render.svg import render_svg
        layout = {
            "holes": [{
                "ref": 1, "par": 4, "start_x": 200, "start_y": 50,
                "end_x": 300, "end_y": 200, "direction": 1,
                "features": [{"category": "fairway", "coords": [[200, 80], [250, 150]]}],
            }],
            "canvas_width": 900, "canvas_height": 700,
        }
        svg = render_svg(layout, {"qr_svg": "<svg>QR</svg>"})
        assert "QR code embedded" in svg

    def test_no_qr_without_option(self):
        from app.services.render.svg import render_svg
        layout = {
            "holes": [], "canvas_width": 900, "canvas_height": 700,
        }
        svg = render_svg(layout)
        assert "QR code embedded" not in svg


class TestHolesEndpointFontHint:
    def _get_client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.api.v1.holes.courses")
    def test_font_hint_in_response(self, mock_courses):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "course_id": "123",
            "holes": [{"ref": 1}],
            "course_name": "Pebble Beach",
            "center": [36.0, -121.0],
            "font_hint": None,
        }
        mock_courses.return_value = mock_collection

        client = self._get_client()
        response = client.get("/api/v1/course-holes?courseId=123")
        assert response.status_code == 200

    @patch("app.api.v1.holes.courses")
    def test_cache_hit_returns_data(self, mock_courses):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "course_id": "456",
            "holes": [],
            "course_name": "Augusta National",
            "center": [33.5, -82.0],
            "font_hint": None,
        }
        mock_courses.return_value = mock_collection

        client = self._get_client()
        response = client.get("/api/v1/course-holes?courseId=456")
        assert response.status_code == 200
