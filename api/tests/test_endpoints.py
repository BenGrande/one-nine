"""Tests for course-holes endpoint."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestCourseHolesEndpoint:
    def _get_client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.api.v1.holes.courses")
    @patch("app.api.v1.holes.fetch_course_map", new_callable=AsyncMock)
    def test_returns_holes(self, mock_fetch, mock_courses):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None
        mock_courses.return_value = mock_collection

        mock_fetch.return_value = {"features": [], "center": [36.0, -121.0]}

        client = self._get_client()
        response = client.get("/api/v1/course-holes?courseId=123&lat=36.0&lng=-121.0")

        assert response.status_code == 200
        data = response.json()
        assert "holes" in data
        assert "center" in data

    @patch("app.api.v1.holes.courses")
    def test_cache_hit(self, mock_courses):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "course_id": "123",
            "holes": [{"ref": 1}],
            "course_name": "Test Course",
            "center": [36.0, -121.0],
            "font_hint": None,
        }
        mock_courses.return_value = mock_collection

        client = self._get_client()
        response = client.get("/api/v1/course-holes?courseId=123")
        assert response.status_code == 200
        data = response.json()
        assert data["course_name"] == "Test Course"

    def test_missing_course_id(self):
        client = self._get_client()
        response = client.get("/api/v1/course-holes")
        assert response.status_code == 422
