import boto3
from botocore.client import Config

from app.core.config import settings

_client = None


def get_s3():
    global _client
    if _client is None:
        kwargs = dict(
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
            kwargs["config"] = Config(signature_version="s3v4")
        _client = boto3.client("s3", **kwargs)
    return _client


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    return get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=expires_in,
    )
