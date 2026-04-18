"""Tests for preorder email + course capture."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestPreorderEndpoints:
    def _get_client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.api.v1.preorder.preorders")
    def test_create_preorder_inserts_when_new(self, mock_preorders):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None
        mock_preorders.return_value = mock_collection

        client = self._get_client()
        response = client.post(
            "/api/v1/preorders",
            json={"email": "Mike@Example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "mike@example.com"
        assert data["id"]
        mock_collection.insert_one.assert_called_once()

    @patch("app.api.v1.preorder.preorders")
    def test_create_preorder_returns_existing(self, mock_preorders):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "id": "abc-123",
            "email": "mike@example.com",
            "course_name": "Pebble Beach",
            "course_id": 42,
            "course_location": "Pebble Beach, CA",
        }
        mock_preorders.return_value = mock_collection

        client = self._get_client()
        response = client.post(
            "/api/v1/preorders",
            json={"email": "mike@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "abc-123"
        assert data["course_name"] == "Pebble Beach"
        mock_collection.insert_one.assert_not_called()

    def test_create_preorder_rejects_invalid_email(self):
        client = self._get_client()
        response = client.post("/api/v1/preorders", json={"email": "not-an-email"})
        assert response.status_code == 422

    @patch("app.api.v1.preorder.preorders")
    def test_update_preorder_course_selected(self, mock_preorders):
        mock_collection = AsyncMock()
        mock_collection.find_one_and_update.return_value = {
            "id": "abc-123",
            "email": "mike@example.com",
            "course_name": "Pebble Beach",
            "course_id": 42,
            "course_location": "Pebble Beach, CA",
        }
        mock_preorders.return_value = mock_collection

        client = self._get_client()
        response = client.patch(
            "/api/v1/preorders/abc-123",
            json={
                "course_name": "Pebble Beach",
                "course_id": 42,
                "course_location": "Pebble Beach, CA",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["course_name"] == "Pebble Beach"
        assert data["course_id"] == 42

    @patch("app.api.v1.preorder.preorders")
    def test_update_preorder_course_free_text(self, mock_preorders):
        mock_collection = AsyncMock()
        mock_collection.find_one_and_update.return_value = {
            "id": "abc-123",
            "email": "mike@example.com",
            "course_name": "My Local Muni",
            "course_id": None,
            "course_location": None,
        }
        mock_preorders.return_value = mock_collection

        client = self._get_client()
        response = client.patch(
            "/api/v1/preorders/abc-123",
            json={"course_name": "My Local Muni"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["course_name"] == "My Local Muni"
        assert data["course_id"] is None

    @patch("app.api.v1.preorder.preorders")
    def test_update_preorder_not_found(self, mock_preorders):
        mock_collection = AsyncMock()
        mock_collection.find_one_and_update.return_value = None
        mock_preorders.return_value = mock_collection

        client = self._get_client()
        response = client.patch(
            "/api/v1/preorders/missing",
            json={"course_name": "Augusta"},
        )
        assert response.status_code == 404
