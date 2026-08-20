import io
import os

from moto import mock_aws
from PIL import Image

# Centralized imports
from app.core.config import settings
from app.core.s3 import get_s3_client
from lambdas.resize_handler import handler as resize_handler
from lambdas.size_calculator import _extract_project_id
from lambdas.size_calculator import handler as size_calculator


@mock_aws
def test_resize_handler_shrinks_large_image() -> None:
    # Set the environment variable for testing
    os.environ["MAX_IMAGE_DIMENSION"] = "500"

    s3 = get_s3_client()
    s3.create_bucket(Bucket=settings.S3_BUCKET_NAME)

    big_image = Image.new("RGB", (2000, 2000), color="red")
    buf = io.BytesIO()
    big_image.save(buf, format="JPEG")
    buf.seek(0)
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key="projects/p1/photo.jpg",
        Body=buf,
        ContentType="image/jpeg",
    )

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": settings.S3_BUCKET_NAME},
                    "object": {"key": "projects/p1/photo.jpg"},
                }
            }
        ]
    }
    resize_handler(event, None)

    resized = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key="projects-resized/p1/photo.jpg")
    resized_image = Image.open(io.BytesIO(resized["Body"].read()))

    assert max(resized_image.size) <= 500

    # Clean up environment variable
    os.environ.pop("MAX_IMAGE_DIMENSION", None)


@mock_aws
def test_resize_handler_ignores_resized_and_non_images() -> None:
    s3 = get_s3_client()
    s3.create_bucket(Bucket=settings.S3_BUCKET_NAME)

    # Put a non-image file
    s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key="projects/p1/notes.txt", Body=b"not an image")

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": settings.S3_BUCKET_NAME},
                    "object": {"key": "projects/p1/notes.txt"},
                }
            }
        ]
    }

    response = resize_handler(event, None)
    assert response["statusCode"] == 200


def test_extract_project_id() -> None:
    valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
    assert _extract_project_id(f"projects/{valid_uuid}/doc.pdf") == valid_uuid
    assert _extract_project_id("projects/invalid-uuid/doc.pdf") is None
    assert _extract_project_id("other/path/file.txt") is None


@mock_aws
def test_size_calculator_quota_auditing() -> None:
    # Dynamically inject mocked DB parameters into Pydantic Settings
    original_limit = settings.MAX_PROJECT_STORAGE_MB
    settings.MAX_PROJECT_STORAGE_MB = 1  # 1 MB Limit for testing

    s3 = get_s3_client()
    s3.create_bucket(Bucket=settings.S3_BUCKET_NAME)

    project_id = "123e4567-e89b-12d3-a456-426614174000"

    # Upload 1MB and 600KB files to simulate a 1.6MB quota breach (Limit is set to 1MB)
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=f"projects/{project_id}/file1.bin",
        Body=b"0" * (1024 * 1024),
    )
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=f"projects/{project_id}/file2.bin",
        Body=b"0" * (600 * 1024),
    )

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": settings.S3_BUCKET_NAME},
                    "object": {"key": f"projects/{project_id}/file2.bin"},
                }
            }
        ]
    }

    # Verify that the handler executes successfully with 0 database requirements
    response = size_calculator(event, None)
    assert response["statusCode"] == 200

    # Restore settings limit
    settings.MAX_PROJECT_STORAGE_MB = original_limit
