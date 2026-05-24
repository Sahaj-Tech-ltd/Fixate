"""Backend abstraction for async task execution.

Cloud mode: Celery task queue (process_document.delay).
Desktop mode: synchronous execution (call directly).
"""

from django.conf import settings


def process_document_async(document_id):
    """Fire-and-forget document processing.

    Cloud: queues via Celery.
    Desktop: runs synchronously, blocking.
    """
    from apps.documents.tasks import process_document

    if settings.FIXATE_MODE == "desktop":
        # Desktop: call the task function directly (synchronous)
        process_document(document_id)
    else:
        # Cloud: dispatch via Celery
        process_document.delay(document_id)
