from pathlib import Path

import cv2
import torch
from torchvision import transforms as T

from tool_dataset import TOOL_DEFINITIONS
from tool_model import ToolPresenceModel


class ToolDetectionService:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = ToolPresenceModel(device=self.device)
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((512, 512)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def health(self):
        return {
            "model_loaded": True,
            "device": str(self.device),
            "tool_count": len(TOOL_DEFINITIONS),
        }

    def analyze_video(self, video_path, sample_seconds=2.0, confidence_threshold=0.5, progress_callback=None):
        self._report_progress(progress_callback, "preprocessing", "数据预处理", "正在读取视频信息并计算采样间隔。", 15)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError("无法打开待分析视频文件。")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if frame_count and fps else 0
        sample_interval = max(1, int(round(fps * max(sample_seconds, 0.25))))
        sample_indices = list(range(0, max(frame_count, 1), sample_interval))

        predictions = []
        per_tool_seconds = {tool_id: 0.0 for tool_id in TOOL_DEFINITIONS}

        self._report_progress(progress_callback, "inference", "模型推理", "正在对采样帧执行器械检测推理。", 25)

        total_samples = max(len(sample_indices), 1)
        for sample_index, frame_index in enumerate(sample_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = cap.read()
            if not success:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tensor = self.transform(frame_rgb).unsqueeze(0).to(self.device)
            probs = self.model.predict(tensor)
            probs_array = probs.squeeze(0).cpu().numpy()

            for tool_id in TOOL_DEFINITIONS:
                conf = float(probs_array[tool_id])
                if conf >= confidence_threshold:
                    per_tool_seconds[tool_id] += sample_interval / fps
                predictions.append({
                    "frameIndex": frame_index,
                    "seconds": round(frame_index / fps, 2),
                    "toolId": tool_id,
                    "toolKey": TOOL_DEFINITIONS[tool_id]["key"],
                    "toolLabel": TOOL_DEFINITIONS[tool_id]["label"],
                    "confidence": round(conf, 4),
                })

            if sample_index == len(sample_indices) - 1 or sample_index % 5 == 0:
                progress = 25 + int(((sample_index + 1) / total_samples) * 60)
                self._report_progress(
                    progress_callback,
                    "inference",
                    "模型推理",
                    f"正在分析采样帧 {sample_index + 1}/{total_samples}。",
                    min(progress, 85),
                )

        cap.release()

        self._report_progress(progress_callback, "postprocessing", "整理结果", "正在汇总器械检测结果。", 92)

        max_seconds = max(per_tool_seconds.values(), default=1)
        instrument_stats = []
        for tool_id in sorted(TOOL_DEFINITIONS.keys()):
            tool_def = TOOL_DEFINITIONS[tool_id]
            seconds = round(min(per_tool_seconds[tool_id], duration), 2)
            instrument_stats.append({
                "toolId": tool_id,
                "key": tool_def["key"],
                "label": tool_def["label"],
                "color": tool_def["color"],
                "seconds": seconds,
                "ratio": round(min(seconds / duration, 1.0), 4) if duration else 0,
                "chartRatio": max(6, round((seconds / max_seconds) * 100)) if max_seconds > 0 else 0,
            })

        self._report_progress(progress_callback, "completed", "检测完成", "器械检测分析完成。", 100)

        return {
            "meta": {
                "fps": round(fps, 2),
                "frameCount": frame_count,
                "durationSeconds": round(duration, 2),
                "sampleSeconds": sample_seconds,
                "sampleCount": len(predictions),
                "device": str(self.device),
                "confidenceThreshold": confidence_threshold,
            },
            "predictions": predictions,
            "instrumentStats": instrument_stats,
        }

    @staticmethod
    def _report_progress(progress_callback, stage, label, message, progress):
        if progress_callback:
            progress_callback(stage, label, message, progress)
