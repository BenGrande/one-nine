"""Game and scoring Pydantic schemas."""

from pydantic import BaseModel, Field


class GlassSetCreate(BaseModel):
    course_id: str
    course_name: str
    glass_count: int = 3
    holes_per_glass: int = 6
    holes: list[dict] = []
    course_lat: float | None = None
    course_lng: float | None = None


class QRCode(BaseModel):
    glass_number: int
    url: str
    qr_svg: str


class GlassSetResponse(BaseModel):
    id: str
    course_id: str
    course_name: str
    glass_count: int
    holes_per_glass: int
    created_at: str
    qr_codes: list[QRCode]


class JoinGameRequest(BaseModel):
    glass_set_id: str
    player_name: str


class JoinGameResponse(BaseModel):
    session_id: str
    player_id: str
    player_name: str


class ScoreSubmit(BaseModel):
    player_id: str
    hole_number: int
    glass_number: int = 1
    score: int = Field(ge=1, le=15)


class LeaderboardEntry(BaseModel):
    player_id: str
    player_name: str
    total_score: int
    holes_played: int
    scores_by_hole: list[dict]


class LeaderboardResponse(BaseModel):
    leaderboard: list[LeaderboardEntry]
    course_name: str
    total_holes: int
