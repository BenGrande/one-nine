"""Static asset endpoints — logo, etc."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

_logo_data_url_cache: str | None = None


def _get_logo_path() -> Path:
    """Resolve logo path relative to project root."""
    # Try several locations
    candidates = [
        Path(__file__).resolve().parents[4] / "public" / "logo.png",
        Path.cwd().parent / "public" / "logo.png",
        Path.cwd() / "public" / "logo.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]  # return first candidate even if missing


@router.get("/assets/logo")
async def get_logo():
    """Return the Split the Tee logo as a base64 data URL."""
    global _logo_data_url_cache
    if _logo_data_url_cache:
        return {"data_url": _logo_data_url_cache}

    logo_path = _get_logo_path()
    if not logo_path.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")

    try:
        data = logo_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        _logo_data_url_cache = f"data:image/png;base64,{b64}"
        return {"data_url": _logo_data_url_cache}
    except Exception as exc:
        logger.error("Failed to read logo: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read logo file")
