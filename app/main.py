import logging

from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routers import auth, documents, projects

logger = logging.getLogger(__name__)

app = FastAPI(title="Projects Dashboard API", version="0.1.0")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ClientError)
def s3_client_error_handler(_request: Request, exc: ClientError) -> JSONResponse:
    # Retrieve the inner AWS error code
    error_code = exc.response.get("Error", {}).get("Code", "Unknown")
    error_message = exc.response.get("Error", {}).get("Message", "S3 Storage error occurred.")

    logger.error(f"S3 ClientError [Code: {error_code}]: {error_message}", exc_info=True)

    if error_code == "ExpiredToken":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Storage credentials have expired. Please contact support."},
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Storage service is temporarily unavailable."},
    )


@app.exception_handler(NoCredentialsError)
def s3_no_credentials_handler(_request: Request, _exc: NoCredentialsError) -> JSONResponse:
    logger.critical("AWS/S3 credentials are completely missing!", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Storage configuration is missing on the server. Please contact support."
        },
    )
