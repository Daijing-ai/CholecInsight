from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from job_manager import PhaseJobManager
from phase_service import PhaseInferenceService


app = FastAPI(title="CholecInsight Phase Analysis API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5180",
        "http://localhost:5180",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_manager = PhaseJobManager(service_factory=PhaseInferenceService)


@app.get("/health")
def health():
    if job_manager.is_service_loaded():
        return job_manager.service.health()

    return {
        "status": "ok",
        "model_loaded": False,
        "message": "Phase inference model will be loaded when the first analysis job runs.",
    }


@app.post("/api/phase/jobs")
async def create_phase_job(
    file: UploadFile = File(...),
    sample_seconds: float = 2.0,
):
    try:
        return await job_manager.create_job_from_upload(file, sample_seconds=sample_seconds)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/phase/jobs/{job_id}")
async def get_phase_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="未找到对应的关键步骤分析任务。")
    return job
