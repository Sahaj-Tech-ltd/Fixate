import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings
from urllib.parse import quote
import uuid


def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version='s3v4')
    )


def generate_upload_key(user_id, filename):
    ext = filename.split('.')[-1].lower()
    return f"uploads/{user_id}/documents/{uuid.uuid4()}.{ext}"


def generate_presigned_upload_url(user_id, filename, expires_in=3600):
    s3_client = get_s3_client()
    key = generate_upload_key(user_id, filename)
    
    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': key,
                'ContentType': 'application/pdf',
            },
            ExpiresIn=expires_in,
        )
        return {
            'url': url,
            'key': key,
            'expires_in': expires_in,
        }
    except ClientError as e:
        raise Exception(f"Failed to generate upload URL: {e}")


def generate_presigned_download_url(key, expires_in=3600):
    s3_client = get_s3_client()
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': key,
            },
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        raise Exception(f"Failed to generate download URL: {e}")


def delete_file_from_s3(key):
    s3_client = get_s3_client()
    
    try:
        s3_client.delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key
        )
        return True
    except ClientError as e:
        raise Exception(f"Failed to delete file: {e}")
