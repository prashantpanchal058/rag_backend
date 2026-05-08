from celery import Celery
import os

# REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.services.tasks"]   # ← explicitly register tasks module
)

celery.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)