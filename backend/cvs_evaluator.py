import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import torch


CVS_CRITERIA = [
    {
        "key": "triangle_clearance",
        "label": "胆囊三角充分暴露",
        "description": "Calot 三角区域内脂肪与纤维组织已被充分分离，肝总管、胆总管连接部清晰可见。",
    },
    {
        "key": "two_structures",
        "label": "仅两条管道进入胆囊",
        "description": "确认仅有胆囊管与胆囊动脉两条结构进入胆囊，排除其他管道误识风险。",
    },
    {
        "key": "liver_bed_separation",
        "label": "胆囊底部与肝床分离",
        "description": "胆囊下 1/3 已从肝床（胆囊板）游离，确保管道识别不受覆盖遮挡。",
    },
]

CVS_STATUS_LEVELS = {
    "achieved": {"label": "已达成", "description": "三条 CVS 标准全部满足，可安全进行夹闭与离断。", "min_score": 3},
    "partial": {"label": "部分达成", "description": "满足 1-2 条 CVS 标准，建议进一步解剖确认后再夹闭。", "min_score": 1},
    "not_achieved": {"label": "未达成", "description": "CVS 标准均未满足，夹闭存在误伤风险，需继续解剖暴露。", "min_score": 0},
}


@dataclass
class CVSEvaluationResult:
    score: int
    status: str
    status_label: str
    status_description: str
    criteria_results: List[Dict[str, Any]] = field(default_factory=list)
    model_used: bool = False
    focus_phase_id: Optional[int] = None
    focus_phase_label: Optional[str] = None


class CVSModel:
    """
    CVS assessment model interface.

    When the trained model is ready, it should implement:
        predict(frames_tensor: torch.Tensor) -> List[Dict]

    Each dict in the returned list should contain:
        - triangle_clearance: float (0-1)
        - two_structures: float (0-1)
        - liver_bed_separation: float (0-1)
        - cvs_score: int (0-3)
        - cvs_achieved: bool
    """

    def __init__(self, device=None, weights_path=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.weights_path = Path(weights_path) if weights_path else None
        self._model_ready = False

    def load_weights(self, weights_path):
        self.weights_path = Path(weights_path)
        self._model_ready = self.weights_path.exists()

    def predict(self, frames_tensor: torch.Tensor) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "CVS model is not yet trained. "
            "Implement predict() with signature: (frames_tensor) -> List[Dict]"
        )

    @property
    def model_ready(self):
        return self._model_ready


class CVSEvaluator:
    def __init__(self, model=None, device=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model or CVSModel(device=self.device)

    def evaluate(
        self,
        frames: List[np.ndarray],
        phase_predictions: Optional[List[Dict[str, Any]]] = None,
        phase_segments: Optional[List[Dict[str, Any]]] = None,
    ) -> CVSEvaluationResult:
        if not frames and not phase_predictions and not phase_segments:
            return self._empty_result()

        if self.model.model_ready and frames:
            calot_frames = self._filter_calot_frames(frames, phase_predictions, phase_segments)
            if calot_frames:
                return self._model_evaluate(calot_frames, phase_predictions, phase_segments)

        return self._placeholder_evaluate(phase_predictions, phase_segments)

    def evaluate_from_video(
        self,
        video_path,
        sample_seconds=2.0,
        phase_result=None,
        progress_callback=None,
    ) -> CVSEvaluationResult:
        phase_predictions = phase_result.get("predictions") if phase_result else None
        phase_segments = phase_result.get("steps") if phase_result else None

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return self.evaluate([], phase_predictions, phase_segments)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sample_interval = max(1, int(round(fps * max(sample_seconds, 0.25))))
        sample_indices = list(range(0, max(frame_count, 1), sample_interval))

        frames = []
        for frame_index in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = cap.read()
            if success:
                frames.append(frame)

        cap.release()

        if progress_callback:
            progress_callback("cvs", "CVS评估", "正在执行 CVS 安全视野评估。", 95)

        return self.evaluate(frames, phase_predictions, phase_segments)

    def _filter_calot_frames(self, frames, phase_predictions, phase_segments):
        calot_phase_id = 1
        if not phase_predictions and not phase_segments:
            return frames

        frame_indices = set()
        if phase_predictions:
            for pred in phase_predictions:
                if pred.get("phaseId") == calot_phase_id:
                    frame_indices.add(pred.get("frameIndex", 0))

        if phase_segments:
            for seg in phase_segments:
                if seg.get("phaseId") == calot_phase_id:
                    frame_indices.add(int(seg.get("startSeconds", 0)))

        if not frame_indices:
            return frames

        match_count = len(frame_indices)
        filtered = [f for i, f in enumerate(frames) if i < match_count]
        return filtered if filtered else frames

    def _model_evaluate(self, frames, phase_predictions, phase_segments):
        tensor = self._frames_to_tensor(frames)
        predictions = self.model.predict(tensor)

        avg_scores = {
            "triangle_clearance": float(np.mean([p["triangle_clearance"] for p in predictions])),
            "two_structures": float(np.mean([p["two_structures"] for p in predictions])),
            "liver_bed_separation": float(np.mean([p["liver_bed_separation"] for p in predictions])),
        }

        return self._build_result(avg_scores, model_used=True)

    def _placeholder_evaluate(self, phase_predictions=None, phase_segments=None):
        has_calot = self._has_calot_phase(phase_predictions, phase_segments)

        if has_calot:
            triangle = round(random.uniform(0.55, 0.85), 3)
            two_struct = round(random.uniform(0.50, 0.80), 3)
            liver_bed = round(random.uniform(0.45, 0.75), 3)
        else:
            triangle = round(random.uniform(0.15, 0.40), 3)
            two_struct = round(random.uniform(0.10, 0.35), 3)
            liver_bed = round(random.uniform(0.10, 0.35), 3)

        avg_scores = {
            "triangle_clearance": triangle,
            "two_structures": two_struct,
            "liver_bed_separation": liver_bed,
        }

        return self._build_result(avg_scores, model_used=False)

    def _build_result(self, avg_scores, model_used=False):
        criteria_results = []
        total_score = 0
        threshold = 0.5

        for criterion in CVS_CRITERIA:
            score = avg_scores.get(criterion["key"], 0.0)
            met = score >= threshold
            if met:
                total_score += 1

            criteria_results.append({
                "key": criterion["key"],
                "label": criterion["label"],
                "description": criterion["description"],
                "score": round(score, 3),
                "met": met,
            })

        status = "not_achieved"
        for level_key in ["achieved", "partial", "not_achieved"]:
            if total_score >= CVS_STATUS_LEVELS[level_key]["min_score"]:
                status = level_key
                break

        status_info = CVS_STATUS_LEVELS[status]

        return CVSEvaluationResult(
            score=total_score,
            status=status,
            status_label=status_info["label"],
            status_description=status_info["description"],
            criteria_results=criteria_results,
            model_used=model_used,
            focus_phase_id=1,
            focus_phase_label="胆囊三角解剖",
        )

    def _has_calot_phase(self, phase_predictions, phase_segments):
        calot_phase_id = 1
        if phase_predictions:
            if any(p.get("phaseId") == calot_phase_id for p in phase_predictions):
                return True
        if phase_segments:
            if any(s.get("phaseId") == calot_phase_id for s in phase_segments):
                return True
        return False

    def _frames_to_tensor(self, frames):
        rgb_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames]
        arrays = [np.transpose(f, (2, 0, 1)).astype(np.float32) / 255.0 for f in rgb_frames]
        return torch.from_numpy(np.stack(arrays)).to(self.device)

    def _empty_result(self):
        status_info = CVS_STATUS_LEVELS["not_achieved"]
        return CVSEvaluationResult(
            score=0,
            status="not_achieved",
            status_label=status_info["label"],
            status_description="无法读取视频帧，CVS 评估未能执行。",
            criteria_results=[
                {"key": c["key"], "label": c["label"], "description": c["description"], "score": 0.0, "met": False}
                for c in CVS_CRITERIA
            ],
            model_used=False,
        )

    def result_to_dict(self, result: CVSEvaluationResult) -> Dict[str, Any]:
        return {
            "score": result.score,
            "status": result.status,
            "statusLabel": result.status_label,
            "statusDescription": result.status_description,
            "criteria": result.criteria_results,
            "modelUsed": result.model_used,
            "focusPhaseId": result.focus_phase_id,
            "focusPhaseLabel": result.focus_phase_label,
        }

    @staticmethod
    def is_ready():
        return False
