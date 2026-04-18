"""Product Pydantic schemas — per-course preorder listings."""

from pydantic import BaseModel, Field


class ProductStats(BaseModel):
    total_par: int
    total_yardage: int
    tee_count: int
    holes: int
    signature_hole: int | None = None
    est_round_minutes: int | None = None


class ProductSummary(BaseModel):
    slug: str
    name: str
    club_name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    par: int | None = None
    yardage: int | None = None
    hero_image: str | None = None


class ProductContent(BaseModel):
    headline: str
    description_html: str
    bullets: list[str] = Field(default_factory=list)


class ProductDetail(ProductSummary):
    course_id: int
    content: ProductContent | None = None
    stats: ProductStats | None = None
    glass3d_url: str | None = None
    patio_image: str | None = None
    gallery: list[str] = Field(default_factory=list)


class ProductsListResponse(BaseModel):
    products: list[ProductSummary]
    total: int
