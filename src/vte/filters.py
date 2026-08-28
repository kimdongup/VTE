from __future__ import annotations

from .config import Config
from .models import TextEvent, iou


def is_logo(event: TextEvent, video_duration: float, ratio: float = 0.8) -> bool:
    """A text event persisting for ``ratio`` of the whole video is a logo/watermark."""
    if video_duration <= 0:
        return False
    return (event.end - event.start) >= video_duration * ratio


def stable_across(events: list[TextEvent], window: float = 5.0) -> bool:
    """Heuristic helper: do consecutive logo candidates keep the same position?"""
    for a, b in zip(events, events[1:]):
        if b.start - a.end > window:
            return False
        if not a.boxes or not b.boxes:
            return False
        if iou(a.boxes[0].pts, b.boxes[0].pts) < 0.8:
            return False
    return True
