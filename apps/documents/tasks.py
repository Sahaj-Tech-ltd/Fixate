import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from celery import shared_task
from django.core.cache import cache
import logging

from apps.documents.models import Document
from apps.users.models import User

logger = logging.getLogger(__name__)


def get_textract_client():
    return boto3.client(
        'textract',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )


def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id):
    try:
        document = Document.objects.select_related('user').get(id=document_id)
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return
    
    if document.status != Document.STATUS_PROCESSING:
        logger.warning(f"Document {document_id} is not in processing status")
        return
    
    try:
        s3_client = get_s3_client()
        textract_client = get_textract_client()
        
        response = s3_client.head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=document.file_key
        )
        file_size = response['ContentLength']
        
        if file_size < 100:
            raise ValueError("File appears to be empty or corrupted")
        
        response = textract_client.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': document.file_key
                }
            }
        )
        
        job_id = response['JobId']
        cache_key = f'textract_job:{document_id}'
        cache.set(cache_key, job_id, timeout=86400)  # 24 hours
        
        check_textract_job.apply_async(args=[document_id, job_id], countdown=5)
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        
        if error_code in ['ProvisionedThroughputExceededException', 'ThrottlingException']:
            logger.warning(f"Textract throttled for document {document_id}, retrying...")
            raise self.retry(exc=e, countdown=60)
        
        logger.error(f"Textract error for document {document_id}: {e}")
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()


@shared_task(bind=True, max_retries=30)
def check_textract_job(self, document_id, job_id):
    try:
        document = Document.objects.select_related('user').get(id=document_id)
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return
    
    try:
        textract_client = get_textract_client()
        
        response = textract_client.get_document_text_detection(JobId=job_id)
        status = response['JobStatus']
        
        if status == 'IN_PROGRESS':
            raise self.retry(countdown=10)
        
        if status == 'FAILED':
            error_message = response.get('StatusMessage', 'OCR processing failed')
            document.status = Document.STATUS_ERROR
            document.error_message = error_message
            document.save()
            logger.error(f"Textract job failed for document {document_id}: {error_message}")
            return
        
        if status == 'SUCCEEDED':
            all_blocks = response['Blocks']
            next_token = response.get('NextToken')
            
            while next_token:
                response = textract_client.get_document_text_detection(
                    JobId=job_id,
                    NextToken=next_token
                )
                all_blocks.extend(response['Blocks'])
                next_token = response.get('NextToken')
            
            text_blocks = [b for b in all_blocks if b['BlockType'] == 'LINE']
            extracted_text = '\n'.join([b['Text'] for b in sorted(text_blocks, key=lambda x: (x.get('Page', 0), x.get('Geometry', {}).get('BoundingBox', {}).get('Top', 0)))])
            
            page_blocks = [b for b in all_blocks if b['BlockType'] == 'PAGE']
            page_count = len(page_blocks)
            
            if len(extracted_text) < 50 and page_count > 0:
                document.status = Document.STATUS_ERROR
                document.error_message = "OCR extracted insufficient text. Document may be empty or contain only images."
                document.save()
                return
            
            document.raw_text = extracted_text
            document.page_count = page_count
            document.word_count = len(extracted_text.split())
            document.status = Document.STATUS_READY
            document.save()
            
            document.user.increment_textract_usage()
            
            logger.info(f"Successfully processed document {document_id}: {document.word_count} words, {page_count} pages")
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        
        if error_code in ['ProvisionedThroughputExceededException', 'ThrottlingException', 'RequestLimitExceeded']:
            logger.warning(f"Textract API throttled for document {document_id}, retrying...")
            raise self.retry(exc=e, countdown=30)
        
        logger.error(f"Error checking textract job for document {document_id}: {e}")
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()
        
    except self.MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for document {document_id}")
        document.status = Document.STATUS_ERROR
        document.error_message = "Processing timed out. Please try again."
        document.save()
        
    except Exception as e:
        logger.error(f"Unexpected error for document {document_id}: {e}")
        document.status = Document.STATUS_ERROR
        document.error_message = str(e)
        document.save()
