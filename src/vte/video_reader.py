from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class FrameSample:
    index: int
    timestamp: float
    image: np.ndarray


class VideoReader:
    def __init__(self, path: str, sample_fps: float = 3.0):
        self.path = path
        self.sample_fps = sample_fps
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"cannot open video: {path}")
        self.src_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = (
            self.frame_count / self.src_fps if self.src_fps > 0 else 0.0
        )
        self._step = max(1, round(self.src_fps / sample_fps)) if sample_fps > 0 else 1

    def __iter__(self):
        idx = 0
        while True:
            ok = self._cap.grab()
            if not ok:
                break
            if idx % self._step == 0:
                ok, frame = self._cap.retrieve()
                if not ok:
                    break
                ts = idx / self.src_fps if self.src_fps > 0 else 0.0
                yield FrameSample(idx, ts, frame)
            idx += 1
        self._cap.release()

    def close(self) -> None:
        self._cap.release()
