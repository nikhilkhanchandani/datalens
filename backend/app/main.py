"""FastAPI application entrypoint.

Keeps `main.py` thin: it only wires together the app, middleware, startup
behavior, error handling, and routers. Route logic lives in `api/routes/`,
business logic lives in `services/` — this file should never grow large as
the project does.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import summarize_validation_errors
from app.api.routes import analysis, cleaning, datasets, health, review
from app.core.config import get_settings
from app.core.exceptions import DataLensError
from app.db.session import init_db

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


is_production = settings.environment.lower() == "production"
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None,
    openapi_url=None if is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DataLensError)
async def handle_datalens_error(request: Request, exc: DataLensError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "message": exc.message},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Anything not expected by a route still gets the app's error shape, and the
    # traceback goes to the server log rather than the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "Something went wrong on the server. Check the server log for details.",
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "InvalidRequestError",
            "message": summarize_validation_errors(exc.errors(), exc.body),
            "details": jsonable_encoder(exc.errors()),
        },
    )


app.include_router(health.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(cleaning.router, prefix="/api")
app.include_router(review.router, prefix="/api")
