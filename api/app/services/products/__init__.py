"""Shared product-page generation helpers.

Used both by the build-time scripts (`scripts/generate_products.py`) and by
the `/api/v1/products` endpoints so the two cannot drift.
"""

from app.services.products.generator import (
    build_glass3d,
    compute_stats,
    default_tee,
    slugify_course,
)

__all__ = ["build_glass3d", "compute_stats", "default_tee", "slugify_course"]
