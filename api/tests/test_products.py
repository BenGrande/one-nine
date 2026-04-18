"""Tests for product endpoints + generator helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.services.products.generator import (
    compute_stats,
    default_tee,
    slugify,
    slugify_course,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Pebble Beach Golf Links") == "pebble-beach-golf-links"

    def test_accents(self):
        assert slugify("Château de l'Île") == "chateau-de-l-ile"

    def test_trims_dashes(self):
        assert slugify("--Hello--World--") == "hello-world"

    def test_course_slug(self):
        c = {
            "name": "Pebble Beach",
            "location": {"city": "Pebble Beach", "state": "CA", "country": "US"},
        }
        assert slugify_course(c) == "pebble-beach-pebble-beach-ca"


class TestStats:
    def test_compute_stats_from_default_tee(self):
        course = {
            "tees": [
                {
                    "tee_name": "White",
                    "gender": "mens",
                    "holes": [
                        {"number": 1, "par": 4, "yardage": 400, "handicap": 3},
                        {"number": 2, "par": 3, "yardage": 200, "handicap": 10},
                        {"number": 3, "par": 5, "yardage": 500, "handicap": 1},
                    ],
                },
            ],
        }
        stats = compute_stats(course)
        assert stats["total_par"] == 12
        assert stats["total_yardage"] == 1100
        assert stats["signature_hole"] == 3
        assert stats["holes"] == 3
        assert stats["est_round_minutes"] == 36

    def test_default_tee_prefers_mens_white(self):
        course = {
            "tees": [
                {"tee_name": "Blue", "gender": "mens", "holes": []},
                {"tee_name": "White", "gender": "mens", "holes": [{"number": 1}]},
            ],
        }
        assert default_tee(course)["tee_name"] == "White"

    def test_default_tee_falls_back_to_first(self):
        course = {"tees": [{"tee_name": "Red", "gender": "womens", "holes": []}]}
        assert default_tee(course)["tee_name"] == "Red"

    def test_stats_empty_course(self):
        stats = compute_stats({})
        assert stats["total_par"] == 0
        assert stats["holes"] == 0


class TestProductsEndpoints:
    def _get_client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.api.v1.products.product_content_coll")
    def test_get_product_404_when_missing(self, mock_coll):
        inst = AsyncMock()
        inst.find_one.return_value = None
        mock_coll.return_value = inst

        response = self._get_client().get("/api/v1/products/no-such-slug")
        assert response.status_code == 404

    @patch("app.api.v1.products.product_content_coll")
    def test_get_product_returns_detail(self, mock_coll):
        inst = AsyncMock()
        inst.find_one.return_value = {
            "slug": "pebble-beach-pebble-beach-ca",
            "course_id": 42,
            "name": "Pebble Beach Golf Links",
            "club_name": "Pebble Beach",
            "city": "Pebble Beach",
            "state": "CA",
            "country": "US",
            "hero_image": "/products/pebble-beach-pebble-beach-ca/glass-front.png",
            "glass3d_url": "/products/pebble-beach-pebble-beach-ca/glass-3d.json",
            "patio_image": "/products/pebble-beach-pebble-beach-ca/patio.jpg",
            "content": {
                "headline": "Play Pebble, pour Pebble.",
                "description_html": "<p>An iconic California course.</p>",
                "bullets": ["Par 72", "6828 yards"],
            },
            "stats": {
                "total_par": 72,
                "total_yardage": 6828,
                "tee_count": 4,
                "holes": 18,
                "signature_hole": 7,
                "est_round_minutes": 216,
            },
        }
        mock_coll.return_value = inst

        response = self._get_client().get("/api/v1/products/pebble-beach-pebble-beach-ca")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "pebble-beach-pebble-beach-ca"
        assert data["stats"]["total_par"] == 72
        assert data["content"]["headline"] == "Play Pebble, pour Pebble."

    @patch("app.api.v1.products.product_content_coll")
    def test_list_products_filters_and_paginates(self, mock_coll):
        inst = MagicMock()
        inst.count_documents = AsyncMock(return_value=1)

        async def _cursor_gen():
            yield {
                "slug": "pebble-beach-pebble-beach-ca",
                "name": "Pebble Beach",
                "city": "Pebble Beach",
                "state": "CA",
                "country": "US",
                "stats": {"total_par": 72, "total_yardage": 6828},
            }

        class _Cursor:
            def __init__(self):
                self._gen = _cursor_gen()

            def sort(self, *_a, **_kw):
                return self

            def skip(self, *_a, **_kw):
                return self

            def limit(self, *_a, **_kw):
                return self

            def __aiter__(self):
                return self._gen

        inst.find = MagicMock(return_value=_Cursor())
        mock_coll.return_value = inst

        response = self._get_client().get("/api/v1/products?state=CA&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["products"]) == 1
        assert data["products"][0]["par"] == 72
