from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.config import get_settings
from app.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
