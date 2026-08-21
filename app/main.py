import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, documents, projects
from app.core import deploy_aws_infrastructure, settings, setup_logging
from app.exceptions import (
    AppError,
    InvalidCredentialsError,
    NotFoundError,
    PermissionDeniedError,
    StorageLimitExceededError,
    UnsupportedFileTypeError,
    UserAlreadyExistsError,
)

setup_logging(
    log_file=settings.LOG_FILE,
    log_level=settings.LOG_LEVEL,
)

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up Projects Dashboard Application...")

    try:
        deploy_aws_infrastructure()

    except Exception as exc:
        logger.error(
            "Startup AWS infrastructure automated deployment skipped or failed: %s",
            exc,
            exc_info=True,
        )

    yield

    logger.info("Shutting down Projects Dashboard Application...")


app = FastAPI(
    title="Projects Dashboard API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


class LatencyLoggingMiddleware(BaseHTTPMiddleware):
    """Measure and log processing latency for every HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Any,
    ) -> Response:
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

        except Exception:
            process_time = (time.perf_counter() - start_time) * 1000

            logger.exception(
                "Method: %s | Path: %s | Unhandled exception | Latency: %.2fms",
                request.method,
                request.url.path,
                process_time,
            )

            raise

        process_time = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Method: %s | Path: %s | Status: %s | Latency: %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

        return response


app.add_middleware(
    LatencyLoggingMiddleware,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


def custom_openapi() -> dict[str, Any]:
    """
    Generate a custom OpenAPI schema.

    Converts application/octet-stream file schemas
    into OpenAPI binary file definitions so Swagger UI
    displays file upload controls correctly.
    """

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    def fix_file_pickers(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("contentMediaType") == "application/octet-stream":
                node.pop(
                    "contentMediaType",
                    None,
                )

                node["format"] = "binary"

            for value in list(node.values()):
                fix_file_pickers(value)

        elif isinstance(node, list):
            for item in node:
                fix_file_pickers(item)

    fix_file_pickers(openapi_schema)

    app.openapi_schema = openapi_schema

    return openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.exception_handler(AppError)
def handle_app_domain_exceptions(
    _request: Request,
    exc: AppError,
) -> JSONResponse:
    if isinstance(
        exc,
        UserAlreadyExistsError,
    ):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
            },
        )

    if isinstance(
        exc,
        InvalidCredentialsError,
    ):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": str(exc),
            },
        )

    if isinstance(
        exc,
        NotFoundError,
    ):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "detail": str(exc),
            },
        )

    if isinstance(
        exc,
        PermissionDeniedError,
    ):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": str(exc),
            },
        )

    if isinstance(
        exc,
        UnsupportedFileTypeError,
    ):
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={
                "detail": str(exc),
            },
        )

    if isinstance(
        exc,
        StorageLimitExceededError,
    ):
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": str(exc),
            },
        )

    logger.exception(
        "Unhandled application domain exception: %s",
        exc,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal application error.",
        },
    )


@app.exception_handler(ClientError)
def s3_client_error_handler(
    _request: Request,
    exc: ClientError,
) -> JSONResponse:
    error_code = exc.response.get(
        "Error",
        {},
    ).get(
        "Code",
        "Unknown",
    )

    error_message = exc.response.get(
        "Error",
        {},
    ).get(
        "Message",
        "S3 Storage error occurred.",
    )

    logger.error(
        "AWS ClientError [Code: %s]: %s",
        error_code,
        error_message,
        exc_info=True,
    )

    if error_code == "ExpiredToken":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": ("Storage credentials have expired. Please contact support.")},
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": ("Storage service is temporarily unavailable.")},
    )


@app.exception_handler(NoCredentialsError)
def s3_no_credentials_handler(
    _request: Request,
    _exc: NoCredentialsError,
) -> JSONResponse:
    logger.critical(
        "AWS/S3 credentials are completely missing!",
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": ("Storage configuration is missing on the server. Please contact support."),
        },
    )


@app.get(
    "/health",
    tags=["system"],
)
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
    }
