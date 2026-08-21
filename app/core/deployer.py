import io
import json
import logging
import os
import subprocess
import tempfile
import time
import zipfile
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger("app.deployer")


# ============================================================
# AWS CLIENTS
# ============================================================

session_kwargs: dict[str, Any] = {
    "region_name": settings.AWS_REGION,
    "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
    "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
}

if settings.AWS_SESSION_TOKEN:
    session_kwargs["aws_session_token"] = settings.AWS_SESSION_TOKEN


s3 = boto3.client("s3", **session_kwargs)
iam = boto3.client("iam", **session_kwargs)
lambda_client = boto3.client("lambda", **session_kwargs)


# ============================================================
# CONSTANTS
# ============================================================

ROLE_NAME = "projects-lambda-execution-role"
RESIZE_FUNC = "projects-image-resizer"
SIZE_FUNC = "projects-quota-calculator"


# ============================================================
# S3 BUCKET
# ============================================================


def ensure_s3_bucket_exists() -> None:
    """Check if the configured S3 bucket exists and create it if missing."""
    bucket_name = settings.S3_BUCKET_NAME

    logger.info("Checking S3 Bucket: '%s'...", bucket_name)

    try:
        s3.head_bucket(Bucket=bucket_name)

        logger.info(
            "S3 Bucket '%s' already exists.",
            bucket_name,
        )

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in ("404", "NoSuchBucket"):
            logger.info(
                "S3 Bucket '%s' not found. Creating it...",
                bucket_name,
            )

            try:
                if settings.AWS_REGION == "us-east-1":
                    s3.create_bucket(
                        Bucket=bucket_name,
                    )
                else:
                    s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={
                            "LocationConstraint": settings.AWS_REGION,
                        },
                    )

                logger.info(
                    "S3 Bucket '%s' created successfully!",
                    bucket_name,
                )

            except ClientError as create_error:
                logger.error(
                    "Failed to create S3 bucket: %s",
                    create_error,
                )
                raise

        else:
            logger.error(
                "S3 HeadBucket Error: %s",
                exc,
            )
            raise


# ============================================================
# IAM ROLE
# ============================================================


def get_or_create_execution_role() -> str:
    """Create or retrieve the Lambda execution IAM role."""
    logger.info("Checking IAM execution roles...")

    try:
        role = iam.get_role(
            RoleName=ROLE_NAME,
        )

        logger.info("Found existing execution role.")

        sts = boto3.client(
            "sts",
            **session_kwargs,
        )

        account_id = sts.get_caller_identity()["Account"]

        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "lambda:InvokeFunction",
                    ],
                    "Resource": (
                        f"arn:aws:lambda:{settings.AWS_REGION}:{account_id}:function:{RESIZE_FUNC}"
                    ),
                }
            ],
        }

        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="AllowInvokeResizeLambda",
            PolicyDocument=json.dumps(policy_document),
        )

        logger.info(
            "Lambda invoke permission configured.",
        )

        return str(role["Role"]["Arn"])

    except iam.exceptions.NoSuchEntityException:
        logger.info(
            "Creating new IAM execution role...",
        )

        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com",
                    },
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(
                assume_role_policy,
            ),
            Description=("Execution role for project dashboard S3 background Lambdas"),
        )

        iam.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn=("arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"),
        )

        iam.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn=("arn:aws:iam::aws:policy/AmazonS3FullAccess"),
        )

        sts = boto3.client(
            "sts",
            **session_kwargs,
        )

        account_id = sts.get_caller_identity()["Account"]

        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "lambda:InvokeFunction",
                    ],
                    "Resource": (
                        f"arn:aws:lambda:{settings.AWS_REGION}:{account_id}:function:{RESIZE_FUNC}"
                    ),
                }
            ],
        }

        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="AllowInvokeResizeLambda",
            PolicyDocument=json.dumps(policy_document),
        )

        logger.info(
            "IAM Role created successfully!",
        )

        return str(role["Role"]["Arn"])


# ============================================================
# LAMBDA ZIP
# ============================================================


def create_zip_payload(filename: str) -> bytes:
    """
    Create Lambda deployment ZIP.

    resize_handler:
        Pillow is installed because image processing requires it.

    size_calculator:
        No external Python dependencies are required.
    """

    buf = io.BytesIO()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.abspath(temp_dir)

        # ----------------------------------------------------
        # Lambda-specific dependencies
        # ----------------------------------------------------

        if filename == "resize_handler":
            requirements = [
                "Pillow",
            ]
        else:
            requirements = []

        # ----------------------------------------------------
        # Install dependencies
        # ----------------------------------------------------

        if requirements:
            logger.info(
                "Installing Lambda dependencies for %s: %s",
                filename,
                ", ".join(requirements),
            )

            subprocess.run(
                [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    temp_path,
                    "--platform",
                    "manylinux_2_28_x86_64",
                    "--implementation",
                    "cp",
                    "--python-version",
                    "3.13",
                    "--only-binary=:all:",
                    "--upgrade",
                    *requirements,
                ],
                check=True,
            )

        # ----------------------------------------------------
        # Create ZIP
        # ----------------------------------------------------

        with zipfile.ZipFile(
            buf,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as zip_file:
            # Add installed dependencies
            for root, _, files in os.walk(temp_path):
                for file_name in files:
                    file_path = os.path.join(
                        root,
                        file_name,
                    )

                    archive_path = os.path.relpath(
                        file_path,
                        temp_path,
                    )

                    zip_file.write(
                        file_path,
                        archive_path,
                    )

            # Add Lambda handler
            handler_path = f"lambdas/{filename}.py"

            if not os.path.exists(handler_path):
                raise FileNotFoundError(f"lambda handler not found: {handler_path}")

            zip_file.write(
                handler_path,
                f"{filename}.py",
            )

    zip_data = buf.getvalue()

    logger.info(
        "Lambda ZIP created for %s. Size: %.2f MB",
        filename,
        len(zip_data) / (1024 * 1024),
    )

    return zip_data


# ============================================================
# LAMBDA DEPLOYMENT
# ============================================================


def deploy_function_with_retry(
    func_name: str,
    handler_name: str,
    zip_data: bytes,
    role_arn: str,
    memory_size: int = 128,
    timeout: int = 30,
) -> str:
    """
    Deploy a Lambda function.

    Updates an existing Lambda or creates a new one.
    Retries creation while IAM role replication is pending.
    """

    logger.info(
        "Deploying Lambda function: %s...",
        func_name,
    )

    try:
        fn = lambda_client.get_function(
            FunctionName=func_name,
        )

        logger.info(
            "Function %s exists. Updating code...",
            func_name,
        )

        lambda_client.update_function_code(
            FunctionName=func_name,
            ZipFile=zip_data,
            Publish=True,
        )

        logger.info(
            "Code updated successfully for %s.",
            func_name,
        )

        return str(
            fn["Configuration"]["FunctionArn"],
        )

    except lambda_client.exceptions.ResourceNotFoundException:
        logger.info(
            "Creating new function %s...",
            func_name,
        )

        for attempt in range(6):
            try:
                fn = lambda_client.create_function(
                    FunctionName=func_name,
                    Runtime="python3.13",
                    Role=role_arn,
                    Handler=f"{handler_name}.handler",
                    Code={
                        "ZipFile": zip_data,
                    },
                    Timeout=timeout,
                    MemorySize=memory_size,
                    Architectures=[
                        "x86_64",
                    ],
                    Publish=True,
                )

                logger.info(
                    "Function %s created successfully!",
                    func_name,
                )

                return str(
                    fn["FunctionArn"],
                )

            except ClientError as exc:
                if "cannot be assumed by Lambda" in str(exc) and attempt < 5:
                    logger.info(
                        "IAM role replication pending. Retrying in 5 seconds (Attempt %s/6)...",
                        attempt + 1,
                    )

                    time.sleep(5)

                else:
                    raise

    raise RuntimeError(
        f"Failed to deploy Lambda function {func_name}",
    )


# ============================================================
# S3 -> LAMBDA PERMISSION
# ============================================================


def grant_s3_invocation_permission(
    func_name: str,
) -> None:
    """Allow S3 to invoke the Lambda function."""

    statement_id = f"AllowS3ToInvoke-{func_name}"

    bucket_arn = f"arn:aws:s3:::{settings.S3_BUCKET_NAME}"

    sts = boto3.client(
        "sts",
        **session_kwargs,
    )

    account_id = sts.get_caller_identity()["Account"]

    try:
        lambda_client.add_permission(
            FunctionName=func_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=bucket_arn,
            SourceAccount=account_id,
        )

        logger.info(
            "S3 permission added to %s.",
            func_name,
        )

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code == "ResourceConflictException":
            logger.info(
                "S3 permission already exists for %s.",
                func_name,
            )
        else:
            raise


# ============================================================
# LAMBDA -> LAMBDA PERMISSION
# ============================================================


def grant_lambda_invoke_permission(
    function_name: str,
) -> None:
    """Allow the quota Lambda to invoke the resize Lambda."""

    statement_id = "AllowQuotaLambdaToInvokeResize"

    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="lambda.amazonaws.com",
        )

        logger.info(
            "Lambda invocation permission added.",
        )

    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceConflictException":
            logger.info(
                "Lambda invocation permission already exists.",
            )
        else:
            raise


# ============================================================
# S3 NOTIFICATION
# ============================================================


def configure_s3_bucket_triggers(
    quota_arn: str,
) -> None:
    """
    Configure S3 notifications.

    Only one Lambda notification is registered
    for the projects/ prefix.
    """

    bucket_name = settings.S3_BUCKET_NAME

    logger.info(
        "Configuring S3 Event Trigger on Bucket '%s'...",
        bucket_name,
    )

    notification_configuration = {
        "LambdaFunctionConfigurations": [
            {
                "Id": "projects-storage-quota-trigger",
                "LambdaFunctionArn": quota_arn,
                "Events": [
                    "s3:ObjectCreated:*",
                    "s3:ObjectRemoved:*",
                ],
                "Filter": {
                    "Key": {
                        "FilterRules": [
                            {
                                "Name": "Prefix",
                                "Value": "projects/",
                            }
                        ]
                    }
                },
            }
        ]
    }

    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_configuration,
        )

        logger.info(
            "S3 Event trigger configured successfully!",
        )

    except ClientError as exc:
        logger.error(
            "Failed to set S3 Notification Configurations: %s",
            exc,
        )
        raise


# ============================================================
# COMPLETE DEPLOYMENT
# ============================================================


def deploy_aws_infrastructure() -> None:
    """
    Run complete serverless infrastructure deployment
    during application startup.
    """

    logger.info(f"{settings.ENV=}")

    if settings.ENV == "test":
        logger.info("Testing environment detected. Skipping physical AWS automated deployment.")
        return

    logger.info("Starting automated AWS serverless infrastructure deployment...")

    try:
        # 1. Ensure S3 bucket exists
        ensure_s3_bucket_exists()

        # 2. Create/get Lambda execution role
        role_arn = get_or_create_execution_role()

        # 3. Deploy image resize Lambda
        resize_zip = create_zip_payload(
            "resize_handler",
        )

        deploy_function_with_retry(
            func_name=RESIZE_FUNC,
            handler_name="resize_handler",
            zip_data=resize_zip,
            role_arn=role_arn,
            memory_size=256,
            timeout=30,
        )

        # 4. Deploy quota calculator Lambda
        size_zip = create_zip_payload(
            "size_calculator",
        )

        quota_arn = deploy_function_with_retry(
            func_name=SIZE_FUNC,
            handler_name="size_calculator",
            zip_data=size_zip,
            role_arn=role_arn,
            memory_size=128,
            timeout=60,
        )

        # 5. Allow S3 to invoke quota Lambda
        grant_s3_invocation_permission(
            SIZE_FUNC,
        )

        # 6. Allow Lambda-to-Lambda invocation
        grant_lambda_invoke_permission(
            RESIZE_FUNC,
        )

        # 7. Configure one S3 trigger
        configure_s3_bucket_triggers(
            quota_arn=quota_arn,
        )

        logger.info("Serverless Cloud infrastructure is fully aligned, automated, and ready!")

    except Exception as exc:
        logger.error(
            "Automated AWS Deployment failed: %s",
            exc,
        )
        raise
