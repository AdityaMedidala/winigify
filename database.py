from datetime import datetime, timezone
from enum import Enum
from typing import Any

import motor.motor_asyncio
from pydantic import BaseModel, Field
from bson import ObjectId

from dotenv import load_dotenv
import os

load_dotenv()

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB_NAME", "financial_analyzer")

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None


def get_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    return _client


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return get_client()[DB_NAME]


def get_jobs_collection() -> motor.motor_asyncio.AsyncIOMotorCollection:
    return get_db()["jobs"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    PENDING    = "pending"     # queued, not started
    PROCESSING = "processing"  # Celery worker picked it up
    DONE       = "done"        # analysis complete
    FAILED     = "failed"      # something went wrong


class JobDocument(BaseModel):
    """
    Represents one analysis job in MongoDB.
    Kept flat intentionally — easy to query, easy to read.
    """
    job_id:        str            # matches Celery task ID for easy cross-reference
    status:        JobStatus      = JobStatus.PENDING
    filename:      str            # original uploaded filename
    query:         str            # user's question / instruction
    result:        str | None     = None   # raw CrewAI output (filled on completion)
    error:         str | None     = None   # error message if status == FAILED
    created_at:    datetime       = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at:  datetime | None = None


# ---------------------------------------------------------------------------
# DB helpers  (called from worker.py and main.py)
# ---------------------------------------------------------------------------

async def create_job(job_id: str, filename: str, query: str) -> None:
    doc = JobDocument(job_id=job_id, filename=filename, query=query)
    await get_jobs_collection().insert_one(doc.model_dump())


async def update_job_processing(job_id: str) -> None:
    await get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {"status": JobStatus.PROCESSING}}
    )


async def update_job_done(job_id: str, result: str) -> None:
    await get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {
            "status":       JobStatus.DONE,
            "result":       result,
            "completed_at": datetime.now(timezone.utc),
        }}
    )


async def update_job_failed(job_id: str, error: str) -> None:
    await get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {
            "status":       JobStatus.FAILED,
            "error":        error,
            "completed_at": datetime.now(timezone.utc),
        }}
    )


async def get_job(job_id: str) -> dict[str, Any] | None:
    doc = await get_jobs_collection().find_one(
        {"job_id": job_id},
        {"_id": 0}   # don't expose the internal Mongo ObjectId
    )
    return doc