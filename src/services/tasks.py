from src.rag.ingestion.index import process_document
from src.services.celery_app import celery

@celery.task(bind=True, max_retries=3, name="tasks.rag_ingestion")
def perform_rag_ingestion_task(self, document_id: str):
    try:
        
        # Update task state to show progress
        self.update_state(state="PROGRESS", meta={"status": "Processing document..."})
        result = process_document(document_id)
        return {
            "status": "success",
            "document_id": document_id,
            "chunks_created": result["chunks_created"],
        }

    except Exception as e:
        raise self.retry(exc=e, countdown=5 * self.request.retries)  # exponential backoff