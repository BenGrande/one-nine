"""Preorder Pydantic schemas."""

from pydantic import BaseModel, Field


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class PreorderCreate(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)


class PreorderCourseUpdate(BaseModel):
    course_name: str = Field(min_length=1, max_length=200)
    course_id: int | None = None
    course_location: str | None = Field(default=None, max_length=200)


class PreorderResponse(BaseModel):
    id: str
    email: str
    course_name: str | None = None
    course_id: int | None = None
    course_location: str | None = None
