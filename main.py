from fastapi import FastAPI, File, UploadFile, Form, HTTPException
import os
import uuid

from crew import run_crew          # moved to crew.py
from database import create_job, get_job

app = FastAPI(title="Financial Document Analyzer")


@app.get("/")
async def root():
    return {"message": "Financial Document Analyzer API is running"}


@app.post("/analyze")
async def api_financial_document(
    file: UploadFile = File(...),
    query: str = Form(default="Analyze this financial document for investment insights"),
):
    job_id    = str(uuid.uuid4())
    file_path = f"data/financial_document_{job_id}.pdf"

    try:
        os.makedirs("data", exist_ok=True)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        if not query or not query.strip():
            query = "Analyze this financial document for investment insights"

        await create_job(
            job_id   = job_id,
            filename = file.filename or "unknown.pdf",
            query    = query.strip(),
        )

        from worker import analyze_document_task
        analyze_document_task.delay(
            job_id    = job_id,
            query     = query.strip(),
            file_path = file_path,
        )

        return {
            "status":  "queued",
            "job_id":  job_id,
            "message": "Analysis started. Poll /results/{job_id} for output.",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error queuing job: {str(e)}")


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    doc = await get_job(job_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return doc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)