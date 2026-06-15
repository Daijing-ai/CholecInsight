from pathlib import Path

import torch

from tool_dataset import TOOL_COUNT
from tool_models import ResNetBaseline


class ToolPresenceModel:
    def __init__(self, device=None, weights_path=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        weights_path = Path(
            weights_path or Path(__file__).resolve().parent / "pretrained_weights" / "tool_best_model.pt"
        )

        if not weights_path.exists():
            raise FileNotFoundError(f"Tool detection weights not found: {weights_path}")

        self.model = ResNetBaseline(backbone='resnet50', num_classes=TOOL_COUNT, pretrained=False)
        state = torch.load(str(weights_path), map_location=self.device, weights_only=False)
        self.model.load_state_dict(state)
        self.model = self.model.to(self.device)
        self.model.eval()

    def predict(self, image_tensor):
        with torch.inference_mode():
            output = self.model(image_tensor)
            probs = torch.sigmoid(output)
        return probs
