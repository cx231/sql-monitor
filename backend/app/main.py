from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.blocking import router as blocking_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.instances import router as instances_router
from app.api.routes.replay import router as replay_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.sqls import router as sqls_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(auth_router, prefix="/api")
    app.include_router(blocking_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(instances_router, prefix="/api")
    app.include_router(replay_router, prefix="/api")
    app.include_router(sessions_router, prefix="/api")
    app.include_router(sqls_router, prefix="/api")
    return app


app = create_app()
