"""Game sessions, players, and score tracking."""

from fastapi import APIRouter, HTTPException

from app.schemas.game import JoinGameRequest, ScoreSubmit
from app.services.game import (
    find_or_create_session,
    add_player,
    get_session,
    get_session_status,
    submit_score,
    delete_score,
    get_leaderboard,
    get_player_scores,
    get_game_history,
    delete_session,
    end_session,
    get_glass_set,
)
from app.services.render.layout import compute_layout, split_into_glasses
from app.services.render.scoring import (
    compute_all_scoring_zones,
    compute_all_terrain_following_zones,
    add_scoring_features_to_layout,
)
from app.services.render.glass_template import compute_glass_template, warp_layout
from app.services.render.svg import render_svg

router = APIRouter()


@router.post("/games/join")
async def join_game(data: JoinGameRequest):
    """Join a game session via QR code scan."""
    try:
        session = await find_or_create_session(data.glass_set_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    player = await add_player(session["id"], data.player_name)

    # Get full session with players
    full_session = await get_session(session["id"])

    return {
        "session_id": session["id"],
        "player_id": player["player_id"],
        "player_name": player["player_name"],
        "course_name": session.get("course_name", ""),
        "glass_count": session.get("glass_count", 3),
        "holes_per_glass": session.get("holes_per_glass", 6),
        "holes": session.get("holes", []),
        "course_map_svg": session.get("course_map_svg", ""),
        "scores": [],
        "players": full_session.get("players", []) if full_session else [],
    }


@router.get("/games/{session_id}")
async def get_game_session(session_id: str):
    """Get full session with players list and course config."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/games/{session_id}/status")
async def get_game_status(session_id: str, player_id: str | None = None):
    """Get session status with holes and optionally player scores (for reconnect)."""
    result = await get_session_status(session_id, player_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.post("/games/{session_id}/score")
async def submit_game_score(session_id: str, data: ScoreSubmit):
    """Submit a score for a hole."""
    if data.score < 1 or data.score > 15:
        raise HTTPException(status_code=400, detail="Score must be between 1 and 15")

    record = await submit_score(
        session_id, data.player_id, data.hole_number, data.glass_number, data.score
    )
    return {"ok": True, "score_record": record}


@router.get("/games/{session_id}/leaderboard")
async def get_game_leaderboard(session_id: str):
    """Get cumulative leaderboard for a game session."""
    try:
        result = await get_leaderboard(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete("/games/{session_id}/score")
async def delete_game_score(session_id: str, player_id: str, hole_number: int):
    """Remove a score for a specific hole."""
    deleted = await delete_score(session_id, player_id, hole_number)
    if not deleted:
        raise HTTPException(status_code=404, detail="Score not found")
    return {"ok": True}


@router.get("/games/{session_id}/scores/{player_id}")
async def get_player_game_scores(session_id: str, player_id: str):
    """Get all scores for a specific player."""
    result = await get_player_scores(session_id, player_id)
    return {"scores": result}


@router.get("/games/glass-set/{glass_set_id}/history")
async def get_glass_set_history(glass_set_id: str):
    """Get all game sessions for a glass set."""
    history = await get_game_history(glass_set_id)
    return {"history": history}


@router.delete("/games/{session_id}")
async def delete_game_session(session_id: str):
    """Delete a game session and all its data."""
    deleted = await delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.post("/games/{session_id}/end")
async def end_game_session(session_id: str):
    """Mark a game session as inactive."""
    ended = await end_session(session_id)
    if not ended:
        raise HTTPException(status_code=404, detail="Session not found or already ended")
    return {"ok": True}


@router.get("/games/{session_id}/glass-3d")
async def get_glass_3d_data(session_id: str, glass_number: int = 1):
    """Get 3D glass rendering data: rect SVG wrap, scoring zones with height fractions, and glass template."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    glass_set_id = session.get("glass_set_id")
    if not glass_set_id:
        raise HTTPException(status_code=400, detail="Session has no glass set")

    glass_set = await get_glass_set(glass_set_id)
    if not glass_set:
        raise HTTPException(status_code=404, detail="Glass set not found")

    glass_count = glass_set.get("glass_count", 3)
    holes_per_glass = glass_set.get("holes_per_glass", 6)

    if glass_number < 1 or glass_number > glass_count:
        raise HTTPException(status_code=400, detail=f"glass_number must be 1-{glass_count}")

    # Use render_holes (full data with features) for the SVG render.
    # Fall back to normalized holes if render_holes not yet stored.
    render_holes = glass_set.get("render_holes") or glass_set.get("holes", [])

    # Split holes for the requested glass
    groups = split_into_glasses(render_holes, glass_count)
    if glass_number - 1 >= len(groups):
        raise HTTPException(status_code=400, detail="Invalid glass number")

    glass_holes = groups[glass_number - 1]

    # Compute layout, zones, then warp to glass space — same pipeline as the designer.
    layout_opts = {
        "canvas_width": 900,
        "canvas_height": 700,
    }
    layout = compute_layout(glass_holes, layout_opts)
    zones_by_hole = compute_all_scoring_zones(layout)
    add_scoring_features_to_layout(layout, zones_by_hole)

    # Compute height fractions BEFORE warping (zone y values are in flat layout space)
    draw_area = layout.get("draw_area", {})
    canvas_top = draw_area.get("top", 0)
    canvas_bottom = draw_area.get("bottom", layout.get("canvas_height", 700))
    canvas_range = canvas_bottom - canvas_top if canvas_bottom != canvas_top else 1

    # Warp layout to glass sector (same as vinyl-preview mode in designer)
    template = compute_glass_template()
    terrain_zones = compute_all_terrain_following_zones(layout)
    warped_layout = warp_layout(layout, template)

    # Render the warped glass-mode SVG — features sized exactly like the designer.
    # Hide background so transparent areas show the 3D glass body underneath.
    tz_dicts = None
    if terrain_zones is not None:
        tz_dicts = [
            [{"score": tz.score, "polygon": tz.polygon,
              "y_center": tz.y_center, "y_top": tz.y_top, "y_bottom": tz.y_bottom,
              "label_position": tz.label_position,
              "leader_line": tz.leader_line}
             for tz in hole_tzs]
            for hole_tzs in terrain_zones
        ]
    svg_opts = {
        "styles": {},
        "hidden_layers": ["background"],
        "per_hole_colors": True,
        "course_name": session.get("course_name", ""),
        "zones_by_hole": zones_by_hole,
        "vinyl_preview": True,
        "show_glass_outline": False,
    }
    if tz_dicts:
        svg_opts["terrain_zones"] = tz_dicts
    wrap_svg = render_svg(warped_layout, svg_opts)

    zones_with_fracs = []
    for hole_zones in zones_by_hole:
        zones_out = []
        for zone in hole_zones.get("zones", []):
            # 0.0 = rim (top of glass), 1.0 = base (bottom of glass)
            frac_top = (zone["y_top"] - canvas_top) / canvas_range
            frac_bottom = (zone["y_bottom"] - canvas_top) / canvas_range
            zones_out.append({
                "score": zone["score"],
                "y_top": zone["y_top"],
                "y_bottom": zone["y_bottom"],
                "label": zone["label"],
                "position": zone.get("position", "above"),
                "height_frac_top": round(frac_top, 4),
                "height_frac_bottom": round(frac_bottom, 4),
            })
        zones_with_fracs.append({
            "hole_ref": hole_zones.get("hole_ref", 0),
            "zones": zones_out,
        })

    return {
        "wrap_svg": wrap_svg,
        "zones_by_hole": zones_with_fracs,
        "glass_template": {
            "glass_height": template["glass_height"],
            "top_radius": template["top_radius"],
            "bottom_radius": template["bottom_radius"],
            "wall_thickness": template["wall_thickness"],
            "base_thickness": template["base_thickness"],
            "inner_r": template["inner_r"],
            "outer_r": template["outer_r"],
            "sector_angle": template["sector_angle"],
            "sector_angle_deg": template["sector_angle_deg"],
            "slant_height": template["slant_height"],
            "volume_ml": template["volume_ml"],
        },
        "holes_per_glass": holes_per_glass,
    }
