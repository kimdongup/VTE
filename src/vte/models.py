"""Core data structures shared across the extraction pipeline.

Role boundaries:

- :class:`TextBox` — geometry (+ detection score) of a text region at a
  single point in time. Knows nothing about time.
- :class:`Track` — the temporal extent of one on-screen text region:
  per-sample boxes plus the accumulated OCR readings. Time-aware.
- :class:`TextEvent` — an export-ready subtitle event produced from a
  finished track. Pure output data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def to_rect(pts: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def iou(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    ax1, ay1, ax2, ay2 = to_rect(a)
    bx1, by1, bx2, by2 = to_rect(b)
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class TextBox:
    pts: list[tuple[float, float]]
    score: float = 1.0

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return to_rect(self.pts)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.rect
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def height(self) -> float:
        x1, y1, x2, y2 = self.rect
        return y2 - y1

    def moved(self, dx: float, dy: float) -> "TextBox":
        return TextBox([(x + dx, y + dy) for x, y in self.pts], self.score)


@dataclass
class Track:
    """A text region followed over time (one subtitle occurrence)."""

    id: int
    boxes: dict[int, TextBox] = field(default_factory=dict)
    texts: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    start_ts: float = 0.0
    end_ts: float = 0.0

    @classmethod
    def starting(
        cls,
        id: int,
        frame_idx: int,
        ts: float,
        box: TextBox,
    ) -> "Track":
        """Create a track whose life begins at ``frame_idx``/``ts``.

        Single factory for the "fresh track taking over a region" case so
        that id / first box / start & end timestamps stay consistent
        between tracker spawn and split hand-over.
        """
        return cls(id=id, boxes={frame_idx: box}, start_ts=ts, end_ts=ts)

    @property
    def last_box(self) -> TextBox | None:
        if not self.boxes:
            return None
        return self.boxes[max(self.boxes)]

    @property
    def duration(self) -> float:
        return self.end_ts - self.start_ts


@dataclass
class TextEvent:
    start: float
    end: float
    text: str
    boxes: list[TextBox] = field(default_factory=list)
    confidence: float = 1.0
