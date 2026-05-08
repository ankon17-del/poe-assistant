from fastapi import FastAPI

from app.api.oauth import router as poe_oauth_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="POE / POE2 Telegram Assistant", version="0.1.0")
    app.include_router(poe_oauth_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
