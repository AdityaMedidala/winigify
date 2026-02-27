import os
from datetime import datetime, timezone

from celery import Celery
from pymongo import MongoClient

from crew import run_crew
from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB_NAME", "financial_analyzer")

celery_app = Celery(
    "financial_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
)

# ---------------------------------------------------------------------------
# Sync MongoDB helpers (PyMongo, not Motor)
#
# Why not Motor here? Motor is async and binds to an event loop at creation.
# Celery workers are synchronous — there's no running event loop to bind to.
# Using Motor here caused "Event loop is closed" errors. PyMongo is the
# correct driver for sync contexts.
# ---------------------------------------------------------------------------

def _get_jobs_collection():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]["jobs"]


def _set_processing(job_id: str) -> None:
    _get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {"status": "processing"}}
    )


def _set_done(job_id: str, result: str) -> None:
    _get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {
            "status":       "done",
            "result":       result,
            "completed_at": datetime.now(timezone.utc),
        }}
    )


def _set_failed(job_id: str, error: str) -> None:
    _get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {
            "status":       "failed",
            "error":        error,
            "completed_at": datetime.now(timezone.utc),
        }}
    )


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="analyze_document")
def analyze_document_task(self, job_id: str, query: str, file_path: str):
    try:
        _set_processing(job_id)
        result = run_crew(query=query, file_path=file_path)

        _set_done(job_id, result)
    except Exception as e:
        _set_failed(job_id, str(e))
        raise
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


