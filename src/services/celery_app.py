from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from the current working directory (or nearest parent)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0").strip()

# rediss:// (TLS) requires an explicit ssl_cert_reqs param, otherwise Celery's
# redis backend raises ValueError at startup. Append it only when using TLS.
def _with_ssl_param(url: str) -> str:
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}ssl_cert_reqs=CERT_REQUIRED"
    return url

BROKER_URL = _with_ssl_param(REDIS_URL)
BACKEND_URL = _with_ssl_param(REDIS_URL)

print(f"[celery_app debug] REDIS_URL repr: {REDIS_URL!r}")
print(f"[celery_app debug] BACKEND_URL repr: {BACKEND_URL!r}")

celery = Celery(
    "tasks",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["src.services.tasks"],  # explicitly register tasks module
)

celery.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)