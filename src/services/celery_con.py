from celery import Celery

celery_app = Celery(
    "rag_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,        # track STARTED state
    result_expires=3600,            # results expire after 1 hour
)