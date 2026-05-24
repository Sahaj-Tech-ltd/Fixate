import logging

from celery import shared_task
from django.core.cache import cache
from django.conf import settings

from apps.documents.models import Document
from apps.users.models import User

logger = logging.getLogger(__name__)


def _get_textract_client():
    import boto3

    return boto3.client(
        "textract",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _get_s3_client():
    import boto3

    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _process_desktop(document):
    """Desktop mode: Tesseract OCR on local file (synchronous).

    Called directly by process_document when FIXATE_MODE=desktop.
    """
    from config.backends import storage, ocr

    file_path = storage.get_local_path(document.file_key)
    result = ocr.extract_text(file_path)

    document.raw_text = result["text"]
    document.page_count = result["pages"]
    document.word_count = result["word_count"]
    document.status = Document.STATUS_READY
    document.save()

    logger.info(
        "Desktop OCR: doc %d — %d words, %d pages",
        document.id,
        result["word_count"],
        result["pages"],
    )


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id):
    try:
        document = Document.objects.select_related("user").get(id=document_id)
    except Document.DoesNotExist:
        logger.error("Document %d not found", document_id)
        return

    if document.status != Document.STATUS_PROCESSING:
        logger.warning("Document %d is not in processing status", document_id)
        return

    # Desktop mode: Tesseract OCR (sync, no retries needed at this level)
    if settings.FIXATE_MODE == "desktop":
        try:
            _process_desktop(document)
        except Exception as e:
            logger.error("Desktop OCR error for document %d: %s", document_id, e)
            document.status = Document.STATUS_ERROR
            document.error_message = str(e)
            document.save()
        return

    # Cloud mode: Textract async flow (existing, unchanged)
    try:
        import boto3
        from botocore.exceptions import ClientError

        s3_client = _get_s3_client()
        textract_client = _get_textract_client()

        response = s3_client.head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=document.file_key,
        )
        file_size = response["ContentLength"]

        if file_size < 100:
            raise ValueError("File appears to be empty or corrupted")

        response = textract_client.start_document_text_detection(
            DocumentLocation={
                "S3Object": {
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": document.file_key,
                }
            }
        )

        job_id = response["JobId"]
        cache_key = f"textract_job:{document_id}"
        cache.set(cache_key, job_id, timeout=86400)  # 24 hours

        check_textract_job.apply_async(args=[document_id, job_id], countdown=5)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code in [
            "ProvisionedThroughputExceededException",
            "ThrottlingException",
        ]:
            logger.warning(
                "Textract throttled for document %d, retrying...", document_id
            )
            raise self.retry(exc=e, countdown=60)

        logger.error("Textract error for document %d: %s", document_id, e)
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()

    except Exception as e:
        logger.error("Error processing document %d: %s", document_id, e)
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()


@shared_task(bind=True, max_retries=30)
def check_textract_job(self, document_id, job_id):
    import boto3
    from botocore.exceptions import ClientError

    try:
        document = Document.objects.select_related("user").get(id=document_id)
    except Document.DoesNotExist:
        logger.error("Document %d not found", document_id)
        return

    try:
        textract_client = _get_textract_client()

        response = textract_client.get_document_text_detection(JobId=job_id)
        status = response["JobStatus"]

        if status == "IN_PROGRESS":
            raise self.retry(countdown=10)

        if status == "FAILED":
            error_message = response.get(
                "StatusMessage", "OCR processing failed"
            )
            document.status = Document.STATUS_ERROR
            document.error_message = error_message
            document.save()
            logger.error(
                "Textract job failed for document %d: %s",
                document_id,
                error_message,
            )
            return

        if status == "SUCCEEDED":
            all_blocks = response["Blocks"]
            next_token = response.get("NextToken")

            while next_token:
                response = textract_client.get_document_text_detection(
                    JobId=job_id, NextToken=next_token
                )
                all_blocks.extend(response["Blocks"])
                next_token = response.get("NextToken")

            # Textract returns blocks in natural reading order (top-to-bottom, left-to-right).
            # No sort needed — sorting by potentially-missing Geometry.BoundingBox.Top is fragile.
            extracted_text = "\n".join(
                b["Text"] for b in all_blocks if b["BlockType"] == "LINE"
            )

            page_blocks = [b for b in all_blocks if b["BlockType"] == "PAGE"]
            page_count = len(page_blocks)

            if len(extracted_text) < 50 and page_count > 0:
                document.status = Document.STATUS_ERROR
                document.error_message = (
                    "OCR extracted insufficient text. "
                    "Document may be empty or contain only images."
                )
                document.save()
                return

            document.raw_text = extracted_text
            document.page_count = page_count
            document.word_count = len(extracted_text.split())
            document.status = Document.STATUS_READY
            document.save()

            document.user.increment_textract_usage()

            logger.info(
                "Successfully processed document %d: %d words, %d pages",
                document_id,
                document.word_count,
                page_count,
            )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code in [
            "ProvisionedThroughputExceededException",
            "ThrottlingException",
            "RequestLimitExceeded",
        ]:
            logger.warning(
                "Textract API throttled for document %d, retrying...",
                document_id,
            )
            raise self.retry(exc=e, countdown=30)

        logger.error(
            "Error checking textract job for document %d: %s",
            document_id,
            e,
        )
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()

    except self.MaxRetriesExceededError:
        logger.error("Max retries exceeded for document %d", document_id)
        document.status = Document.STATUS_ERROR
        document.error_message = "Processing timed out. Please try again."
        document.save()

    except Exception as e:
        logger.error(
            "Unexpected error for document %d: %s", document_id, e
        )
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()
