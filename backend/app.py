from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
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

service = PhaseInferenceService()
job_manager = PhaseJobManager(service)


@app.get("/health")
def health():
    return service.health()


@app.post("/api/phase/jobs")
async def create_phase_job(
    request: Request,
    sample_seconds: float = 2.0,
    x_file_name: Optional[str] = Header(default=None),
):
    try:
        raw_content = await request.body()
        if not raw_content:
            raise HTTPException(status_code=400, detail="上传内容为空。")

        return job_manager.create_job(raw_content, x_file_name or "video.mp4", sample_seconds=sample_seconds)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/phase/jobs/{job_id}")
async def get_phase_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="未找到对应的关键步骤分析任务。")
    return job
