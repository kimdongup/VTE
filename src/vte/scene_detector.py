from __future__ import annotations

import cv2
import numpy as np

from .models import iou


def frame_diff(prev: np.ndarray, cur: np.ndarray) -> float:
    """Return a normalized difference score in [0, 1] between two frames.

    Uses downscaled grayscale mean absolute difference.
    """
    size = (64, 36)
    a = cv2.resize(cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY), size)
    b = cv2.resize(cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY), size)
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))) / 255.0)


def boxes_changed(
    prev_boxes: list[list[tuple[float, float]]],
    cur_boxes: list[list[tuple[float, float]]],
    iou_threshold: float = 0.3,
) -> bool:
    """True when the text-region layout changed enough to warrant re-detection."""
    if len(prev_boxes) != len(cur_boxes):
        return True
    used = set()
    for prev in prev_boxes:
        best, best_iou = -1, iou_threshold
        for j, cur in enumerate(cur_boxes):
            if j in used:
                continue
            score = iou(prev, cur)
            if score > best_iou:
                best_iou, best = score, j
        if best < 0:
            return True
        used.add(best)
    return False


class SceneDetector:
    """Skip re-processing of static segments.

    Returns False from ``should_process`` only when the previous processed
    frame was nearly identical AND the tracked box layout is unchanged.
    """

    def __init__(self, threshold: float = 0.12, layout_threshold: float = 0.3):
        self.threshold = threshold
        self.layout_threshold = layout_threshold
        self._prev_frame: np.ndarray | None = None
        self._prev_layout: list[list[tuple[float, float]]] = []

    def should_process(
        self,
        frame: np.ndarray,
        layout: list[list[tuple[float, float]]] | None = None,
    ) -> bool:
        if self._prev_frame is None:
            self._prev_frame = frame
            if layout is not None:
                self._prev_layout = layout
            return True
        diff = frame_diff(self._prev_frame, frame)
        if layout is not None:
            changed = boxes_changed(self._prev_layout, layout, self.layout_threshold)
            self._prev_layout = layout
        else:
            changed = False
        self._prev_frame = frame
        return diff >= self.threshold or changed
