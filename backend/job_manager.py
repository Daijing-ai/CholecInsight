import json
import threading
import uuid
from datetime import datetime
from pathlib import Path


class PhaseJobManager:
    def __init__(self, service, runtime_dir=None):
        self.service = service
        self.runtime_dir = Path(runtime_dir or Path(__file__).resolve().parent / "runtime")
        self.jobs_dir = self.runtime_dir / "jobs"
        self.uploads_dir = self.runtime_dir / "uploads"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create_job(self, file_bytes, file_name, sample_seconds=2.0):
        job_id = f"phase-job-{uuid.uuid4().hex}"
        suffix = Path(file_name or "video.mp4").suffix or ".mp4"
        video_path = self.uploads_dir / f"{job_id}{suffix}"
        video_path.write_bytes(file_bytes)

        job = {
            "jobId": job_id,
            "status": "queued",
            "fileName": file_name or "video.mp4",
            "sampleSeconds": sample_seconds,
            "createdAt": self._now(),
            "updatedAt": self._now(),
            "result": None,
            "error": None,
            "videoPath": str(video_path),
        }
        self._save_job(job)

        worker = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        worker.start()
        return self._public_job(job)

    def get_job(self, job_id):
        job = self._load_job(job_id)
        if not job:
            return None
        return self._public_job(job)

    def _run_job(self, job_id):
        job = self._load_job(job_id)
        if not job:
            return

        job["status"] = "running"
        job["updatedAt"] = self._now()
        self._save_job(job)

        try:
            result = self.service.analyze_video(job["videoPath"], sample_seconds=job.get("sampleSeconds", 2.0))
            job["status"] = "completed"
            job["result"] = result
            job["updatedAt"] = self._now()
            self._save_job(job)
        except Exception as exc:  # noqa: BLE001
            job["status"] = "failed"
            job["error"] = str(exc)
            job["updatedAt"] = self._now()
            self._save_job(job)

    def _job_file(self, job_id):
        return self.jobs_dir / f"{job_id}.json"

    def _load_job(self, job_id):
        job_file = self._job_file(job_id)
        if not job_file.exists():
            return None
        with job_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save_job(self, job):
        with self._lock:
            job_file = self._job_file(job["jobId"])
            with job_file.open("w", encoding="utf-8") as file:
                json.dump(job, file, ensure_ascii=False, indent=2)

    def _public_job(self, job):
        return {
            "jobId": job["jobId"],
            "status": job["status"],
            "fileName": job.get("fileName"),
            "sampleSeconds": job.get("sampleSeconds"),
            "createdAt": job.get("createdAt"),
            "updatedAt": job.get("updatedAt"),
            "result": job.get("result"),
            "error": job.get("error"),
        }

    @staticmethod
    def _now():
        return datetime.now().isoformat()
