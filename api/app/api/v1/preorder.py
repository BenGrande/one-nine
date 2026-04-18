"""Preorder email capture + course interest."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo import ReturnDocument

from app.db.mongo import preorders
from app.schemas.preorder import (
    PreorderCourseUpdate,
    PreorderCreate,
    PreorderResponse,
)

router = APIRouter()


def _serialize(doc: dict) -> PreorderResponse:
    return PreorderResponse(
        id=doc["id"],
        email=doc["email"],
        course_name=doc.get("course_name"),
        course_id=doc.get("course_id"),
        course_location=doc.get("course_location"),
    )


@router.post("/preorders", response_model=PreorderResponse)
async def create_preorder(data: PreorderCreate):
    """Create (or return existing) preorder by email."""
    email = data.email.strip().lower()
    collection = preorders()

    existing = await collection.find_one({"email": email})
    if existing:
        return _serialize(existing)

    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "created_at": datetime.now(timezone.utc),
    }
    await collection.insert_one(doc)
    return _serialize(doc)


@router.patch("/preorders/{preorder_id}", response_model=PreorderResponse)
async def update_preorder_course(preorder_id: str, data: PreorderCourseUpdate):
    """Attach course-of-interest to an existing preorder."""
    collection = preorders()
    updates = {
        "course_name": data.course_name.strip(),
        "course_id": data.course_id,
        "course_location": data.course_location,
        "course_added_at": datetime.now(timezone.utc),
    }
    result = await collection.find_one_and_update(
        {"id": preorder_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Preorder not found")
    return _serialize(result)
