from __future__ import annotations

from typing import TYPE_CHECKING

import boto3

from app.core import settings

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client


def get_s3_client() -> S3Client:
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_session_token=settings.AWS_SESSION_TOKEN or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        endpoint_url=settings.S3_ENDPOINT_URL or None,
    )
