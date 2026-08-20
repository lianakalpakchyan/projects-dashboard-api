import io
import logging
import os
from typing import Any
from urllib.parse import unquote_plus

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


DEFAULT_MAX_IMAGE_DIMENSION = 1024

IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
)


def _get_s3_client() -> Any:
    """
    Create an S3 client when the handler runs.

    Creating the client inside the handler is important for tests
    using Moto's @mock_aws because the AWS mock must already be active
    when the client is created.
    """

    return boto3.client(
        "s3",
        region_name=os.getenv(
            "AWS_REGION",
            "us-east-1",
        ),
    )


def handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """
    Process images uploaded to projects/.

    The resized image is stored in projects-resized/.
    """

    logger.info("Image resize Lambda started.")

    s3 = _get_s3_client()

    # Pillow is packaged directly into the Lambda ZIP.
    try:
        from PIL import Image
    except ImportError:
        logger.exception("Pillow is not installed in the Lambda deployment package.")

        return {
            "statusCode": 500,
            "body": ("Image resizing failed because Pillow (PIL) is not installed."),
        }

    records = event.get(
        "Records",
        [],
    )

    if not records:
        logger.warning("No S3 Records found in event.")

        return {
            "statusCode": 400,
            "body": "No S3 Records found in event.",
        }

    processed = 0
    skipped = 0
    failed = 0

    for record in records:
        try:
            if "s3" not in record:
                skipped += 1
                continue

            bucket = record["s3"]["bucket"]["name"]

            raw_key = record["s3"]["object"]["key"]

            key = unquote_plus(raw_key)

            logger.info(
                "Processing s3://%s/%s",
                bucket,
                key,
            )

            # Never process already-resized images.
            if key.startswith("projects-resized/"):
                skipped += 1
                continue

            # Only process files under projects/.
            if not key.startswith("projects/"):
                skipped += 1
                continue

            # Only process supported image types.
            if not key.lower().endswith(IMAGE_EXTENSIONS):
                skipped += 1
                continue

            # Download original image.
            obj = s3.get_object(
                Bucket=bucket,
                Key=key,
            )

            image_bytes = obj["Body"].read()

            logger.info(
                "Downloaded %s bytes.",
                len(image_bytes),
            )

            # Open image.
            image = Image.open(
                io.BytesIO(image_bytes),
            )

            image.load()

            img_format = image.format or ("PNG" if key.lower().endswith(".png") else "JPEG")

            logger.info(
                "Image format: %s",
                img_format,
            )

            # JPEG cannot save RGBA/LA/P modes.
            if img_format.upper() == "JPEG" and image.mode in (
                "RGBA",
                "LA",
                "P",
            ):
                image = image.convert("RGB")

            # Get maximum dimension from environment.
            max_image_dimension = int(
                os.getenv(
                    "MAX_IMAGE_DIMENSION",
                    DEFAULT_MAX_IMAGE_DIMENSION,
                )
            )

            # Resize while preserving aspect ratio.
            image.thumbnail(
                (
                    max_image_dimension,
                    max_image_dimension,
                ),
                Image.Resampling.LANCZOS,
            )

            logger.info(
                "Resized image to %sx%s.",
                image.width,
                image.height,
            )

            # Save resized image to memory.
            buffer = io.BytesIO()

            if img_format.upper() == "JPEG":
                save_kwargs = {
                    "quality": 85,
                    "optimize": True,
                }
            else:
                save_kwargs = {
                    "optimize": True,
                }

            image.save(
                buffer,
                format=img_format,
                **save_kwargs,
            )

            buffer.seek(0)

            # projects/foo.jpg
            # becomes
            # projects-resized/foo.jpg
            destination_key = "projects-resized/" + key[len("projects/") :]

            content_type = obj.get(
                "ContentType",
                f"image/{img_format.lower()}",
            )

            # Upload resized image.
            s3.put_object(
                Bucket=bucket,
                Key=destination_key,
                Body=buffer.getvalue(),
                ContentType=content_type,
            )

            logger.info(
                "Uploaded resized image to s3://%s/%s",
                bucket,
                destination_key,
            )

            processed += 1

        except Exception:
            failed += 1

            logger.exception(
                "Failed to process S3 record.",
            )

    return {
        "statusCode": 200,
        "body": (
            f"Image resizing complete. Processed={processed}, Skipped={skipped}, Failed={failed}"
        ),
    }
