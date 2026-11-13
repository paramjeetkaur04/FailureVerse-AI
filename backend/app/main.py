"""Phase 1 API. No Docker access, LLM invocation, or infrastructure mutations."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.database import Base, create_database
from app.services.health import HealthService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, demo_transport=None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_database(settings.database_url)
        app.state.engine = engine
        Base.metadata.create_all(engine)
        app.state.health_service = HealthService(engine, settings, demo_transport)
        try:
            await app.state.health_service.collect("startup")
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="FailureVerse AI", version="0.1.0",
        description="Phase 1: local service health, saved checks, and public configuration.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    registry = CollectorRegistry()
    requests = Counter(
        "failureverse_http_requests_total", "Completed API requests", ["method", "route", "status"],
        registry=registry,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=False,
    )

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        requests.labels(request.method, route.path if route else "unmatched", response.status_code).inc()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Database is unavailable. Check backend storage."})

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    app.include_router(router)
    return app


app = create_app()
