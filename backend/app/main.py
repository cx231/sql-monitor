from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
