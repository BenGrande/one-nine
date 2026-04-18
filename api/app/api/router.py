from fastapi import APIRouter

from app.api.v1 import search, holes, settings, games, qr, render, assets, preorder

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(search.router, tags=["search"])
api_router.include_router(holes.router, tags=["holes"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(games.router, tags=["games"])
api_router.include_router(qr.router, tags=["qr"])
api_router.include_router(render.router, tags=["render"])
api_router.include_router(assets.router, tags=["assets"])
api_router.include_router(preorder.router, tags=["preorder"])
