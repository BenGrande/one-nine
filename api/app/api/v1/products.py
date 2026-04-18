"""Product listing + detail endpoints.

Content is populated by `scripts/generate_products.py`; these endpoints serve
the precomputed `product_content` collection.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.mongo import product_content as product_content_coll
from app.schemas.product import (
    ProductContent,
    ProductDetail,
    ProductStats,
    ProductSummary,
    ProductsListResponse,
)

router = APIRouter()


def _to_summary(doc: dict) -> ProductSummary:
    return ProductSummary(
        slug=doc["slug"],
        name=doc.get("name") or doc.get("club_name") or doc["slug"],
        club_name=doc.get("club_name"),
        city=doc.get("city"),
        state=doc.get("state"),
        country=doc.get("country"),
        par=doc.get("stats", {}).get("total_par"),
        yardage=doc.get("stats", {}).get("total_yardage"),
        hero_image=doc.get("hero_image"),
    )


def _to_detail(doc: dict) -> ProductDetail:
    content_dict = doc.get("content") or {}
    content = ProductContent(**content_dict) if content_dict else None
    stats_dict = doc.get("stats") or {}
    stats = ProductStats(**stats_dict) if stats_dict else None
    base = _to_summary(doc).model_dump()
    base.update({
        "course_id": doc.get("course_id", 0),
        "content": content,
        "stats": stats,
        "glass3d_url": doc.get("glass3d_url"),
        "patio_image": doc.get("patio_image"),
        "gallery": doc.get("gallery", []),
    })
    return ProductDetail(**base)


@router.get("/products", response_model=ProductsListResponse)
async def list_products(
    q: str | None = Query(default=None, max_length=120),
    state: str | None = Query(default=None, max_length=3),
    country: str | None = Query(default=None, max_length=3),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    coll = product_content_coll()
    query: dict = {}
    if state:
        query["state"] = state.upper()
    if country:
        query["country"] = country.upper()
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"club_name": {"$regex": q, "$options": "i"}},
            {"city": {"$regex": q, "$options": "i"}},
        ]
    total = await coll.count_documents(query)
    cursor = coll.find(query).sort("name", 1).skip(offset).limit(limit)
    items = [_to_summary(doc) async for doc in cursor]
    return ProductsListResponse(products=items, total=total)


@router.get("/products/{slug}", response_model=ProductDetail)
async def get_product(slug: str):
    coll = product_content_coll()
    doc = await coll.find_one({"slug": slug})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return _to_detail(doc)
