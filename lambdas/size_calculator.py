import json
import logging
import os
import re
from typing import Any
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_REGION = os.getenv(
    "AWS_REGION",
    "us-east-1",
)

RESIZE_FUNCTION_NAME = os.getenv(
    "RESIZE_FUNCTION_NAME",
    "projects-image-resizer",
)

MAX_PROJECT_STORAGE_MB = int(
    os.getenv(
        "MAX_PROJECT_STORAGE_MB",
        "500",
    )
)

IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
)


PROJECT_ID_REGEX = re.compile(
    r"^projects/([a-f0-9\-]{36})/",
    re.IGNORECASE,
)


# ============================================================
# AWS CLIENTS
# ============================================================

lambda_client = boto3.client(
    "lambda",
    region_name=DEFAULT_REGION,
)


# ============================================================
# HELPERS
# ============================================================


def _get_s3_client(
    region: str | None = None,
) -> Any:
    """
    Create an S3 client for the specified region.

    If no region is provided, use the Lambda region.
    """

    return boto3.client(
        "s3",
        region_name=region or DEFAULT_REGION,
    )


def _get_bucket_region(
    bucket: str,
) -> str:
    """
    Determine the actual AWS region of an S3 bucket.

    S3 returns:
        None / empty string -> us-east-1
        us-west-2 -> us-west-2
        eu-west-1 -> eu-west-1
        etc.
    """

    # get_bucket_location works through the S3
    # global endpoint.
    global_s3 = boto3.client(
        "s3",
        region_name="us-east-1",
    )

    response = global_s3.get_bucket_location(
        Bucket=bucket,
    )

    location = response.get("LocationConstraint")

    if not location:
        return "us-east-1"

    # AWS historically returns this value
    # for US East (N. Virginia).
    if location == "EU":
        return "eu-west-1"

    return str(location)


def _extract_project_id(
    key: str,
) -> str | None:
    """
    Extract project UUID from:

        projects/<uuid>/...
    """

    match = PROJECT_ID_REGEX.match(key)

    if match:
        return match.group(1)

    return None


def _is_image(
    key: str,
) -> bool:
    """Return True if the S3 key is a supported image."""

    return key.lower().endswith(IMAGE_EXTENSIONS)


def _invoke_resize_lambda(
    event: dict[str, Any],
) -> None:
    """
    Invoke image resize Lambda asynchronously.
    """

    logger.info(
        "Invoking resize Lambda: %s",
        RESIZE_FUNCTION_NAME,
    )

    lambda_client.invoke(
        FunctionName=RESIZE_FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps(event).encode("utf-8"),
    )

    logger.info(
        "Resize Lambda invocation submitted.",
    )


def _calculate_project_storage(
    bucket: str,
    project_id: str,
) -> int:
    """
    Calculate total storage used by a project.

    The S3 client is created using the bucket's
    actual region.
    """

    bucket_region = _get_bucket_region(bucket)

    logger.info(
        "S3 bucket '%s' is located in region '%s'.",
        bucket,
        bucket_region,
    )

    s3 = _get_s3_client(bucket_region)

    prefix = f"projects/{project_id}/"

    total_bytes = 0

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
    ):
        for item in page.get(
            "Contents",
            [],
        ):
            total_bytes += int(item["Size"])

    return total_bytes


# ============================================================
# HANDLER
# ============================================================


def handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """
    Triggered by S3 ObjectCreated/ObjectRemoved events.

    Responsibilities:

    1. Check project storage quota.
    2. If an uploaded object is an image,
       invoke the resize Lambda asynchronously.
    """

    logger.info("Storage quota Lambda started.")

    records = event.get(
        "Records",
        [],
    )

    if not records:
        logger.warning("No S3 Records found in event.")

        return {
            "statusCode": 400,
            "body": ("No S3 Records found in event."),
        }

    processed = 0
    resize_invocations = 0
    skipped = 0
    failed = 0

    for record in records:
        try:
            # ------------------------------------------------
            # Validate S3 record
            # ------------------------------------------------

            if "s3" not in record:
                logger.warning("Skipping record without S3 information.")

                skipped += 1
                continue

            event_name = record.get(
                "eventName",
                "",
            )

            bucket = record["s3"]["bucket"]["name"]

            raw_key = record["s3"]["object"]["key"]

            key = unquote_plus(raw_key)

            logger.info(
                "S3 event: %s | Bucket: %s | Key: %s",
                event_name,
                bucket,
                key,
            )

            # ------------------------------------------------
            # IMAGE RESIZE
            # ------------------------------------------------

            if (
                event_name.startswith("ObjectCreated:")
                and key.startswith("projects/")
                and _is_image(key)
            ):
                _invoke_resize_lambda({"Records": [record]})

                resize_invocations += 1

            # ------------------------------------------------
            # PROJECT ID
            # ------------------------------------------------

            project_id = _extract_project_id(key)

            if not project_id:
                logger.info(
                    "Could not extract project ID from key: %s",
                    key,
                )

                skipped += 1
                continue

            logger.info(
                "Checking storage quota for project: %s",
                project_id,
            )

            # ------------------------------------------------
            # STORAGE
            # ------------------------------------------------

            total_bytes = _calculate_project_storage(
                bucket=bucket,
                project_id=project_id,
            )

            limit_bytes = MAX_PROJECT_STORAGE_MB * 1024 * 1024

            mb_used = total_bytes / (1024 * 1024)

            logger.info(
                "Storage Quota Audit: Project %s is using %.2f MB of %s MB limit.",
                project_id,
                mb_used,
                MAX_PROJECT_STORAGE_MB,
            )

            # ------------------------------------------------
            # QUOTA CHECK
            # ------------------------------------------------

            if total_bytes > limit_bytes:
                logger.warning(
                    "QUOTA EXCEEDED! "
                    "Project %s has exceeded "
                    "its storage quota: "
                    "%d bytes used "
                    "(Limit: %d bytes).",
                    project_id,
                    total_bytes,
                    limit_bytes,
                )
            else:
                logger.info(
                    "Quota check passed for Project %s.",
                    project_id,
                )

            processed += 1

        except ClientError as exc:
            failed += 1

            error_code = exc.response.get("Error", {}).get("Code", "Unknown")

            logger.error(
                "AWS error while processing bucket=%s key=%s: %s",
                bucket if "bucket" in locals() else "unknown",
                key if "key" in locals() else "unknown",
                error_code,
            )

            logger.exception("Full AWS error details:")

        except Exception:
            failed += 1

            logger.exception("Failed to process S3 record.")

    # ========================================================
    # SUMMARY
    # ========================================================

    logger.info(
        "Quota Lambda summary: processed=%d resize_invocations=%d skipped=%d failed=%d",
        processed,
        resize_invocations,
        skipped,
        failed,
    )

    return {
        "statusCode": 200,
        "body": (
            "Storage quota analysis synced successfully. "
            f"Processed={processed}, "
            f"ResizeInvocations={resize_invocations}, "
            f"Skipped={skipped}, "
            f"Failed={failed}"
        ),
    }
