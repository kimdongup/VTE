"""TextDetector 옵션 규약 단위테스트 (엔진은 mock, 실 OCR 없음).

coder가 구현 중인 옵션의 계약을 고정한다:

- ``det_max_width``: 프레임을 detect 입력 전에 다운스케일하더라도 반환되는
  bbox는 **반드시 원본 프레임 좌표계**로 복원되어야 한다. 엔진이 축소된
  좌표계의 box를 반환했다고 가정하고 배율 복원을 검증한다.
- ``roi_band=(0.6, 1.0)`` + ``det_max_width`` 조합: y 범위 필터(밴드 크롭)와
  좌표 복원(다운스케일 배율 + y 오프셋)이 동시에 성립해야 한다.
- 옵션 None: 원본 이미지가 그대로 엔진에 들어가고 좌표도 무변경 통과.

box 높이 필터(min/max_box_height)는 복원된 좌표 기준으로 적용되어야 한다
(축소 좌표 기준으로 필터하면 작은 텍스트가 잘려나감). 첫 테스트의 fixture
poly는 이 순서까지 구별하도록 설계되었다: 축소 높이 6(<min_box_height=8),
복원 높이 18(허용 범위).
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from vte.config import Config
from vte.detector import TextDetector
from vte.models import TextBox


class _FakeDetEngine:
    """predict에 들어온 이미지 좌표계로 고정 poly를 반환하는 mock 엔진."""

    def __init__(self, poly, score: float = 0.9):
        self._poly = poly
        self._score = score
        self.seen_shapes: list[tuple[int, ...]] = []

    def predict(self, image):
        self.seen_shapes.append(tuple(image.shape))
        return [
            {
                "dt_polys": [[(float(x), float(y)) for x, y in self._poly]],
                "dt_scores": [self._score],
            }
        ]


def _detector_with(cfg: Config, poly) -> tuple[TextDetector, _FakeDetEngine]:
    det = TextDetector(cfg)
    engine = _FakeDetEngine(poly)
    det._engine = engine  # lazy 초기화 우회: PaddleOCR 로딩 없음
    return det, engine


def _frame(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _pts_close(actual: TextBox, expected, tol: float = 0.75) -> bool:
    return len(actual.pts) == len(expected) and all(
        abs(ax - ex) <= tol and abs(ay - ey) <= tol
        for (ax, ay), (ex, ey) in zip(actual.pts, expected)
    )


# --- det_max_width: 축소 좌표계 -> 원본 좌표계 복원 -----------------------

# 엔진 입력(640x360로 축소됨) 좌표계의 poly. 높이 6은 축소 좌표 기준으로는
# min_box_height(8) 미만이지만 복원 후에는 18이므로, "복원 후 필터" 순서만 통과.
_SCALED_POLY = [(10.0, 20.0), (110.0, 20.0), (110.0, 26.0), (10.0, 26.0)]
_ORIGINAL_EXPECTED = [(30.0, 60.0), (330.0, 60.0), (330.0, 78.0), (30.0, 78.0)]


def test_det_max_width_restores_original_coords():
    cfg = replace(Config(), det_max_width=640)
    det, engine = _detector_with(cfg, _SCALED_POLY)

    boxes = det.detect(_frame(1080, 1920))

    # 엔진에는 축소된 이미지가 들어가야 한다 (규약: 다운스케일 후 detect)
    assert engine.seen_shapes, "engine.predict가 호출되지 않음"
    seen_h, seen_w = engine.seen_shapes[0][:2]
    assert seen_w <= 640
    assert abs(seen_h - 1080 * (seen_w / 1920)) <= 1.0  # 종횡비 유지

    assert len(boxes) == 1
    assert _pts_close(boxes[0], _ORIGINAL_EXPECTED)


def test_det_max_width_with_roi_band_combo():
    # roi_band=(0.6, 1.0) -> y 648~1080 크롭(높이 432), 폭 1920 -> 640 (배율 3)
    cfg = replace(Config(), roi_band=(0.6, 1.0), det_max_width=640)
    scaled_poly = [(5.0, 10.0), (100.0, 10.0), (100.0, 40.0), (5.0, 40.0)]
    # 원본 좌표: x*3, y*3 + 648
    expected = [(15.0, 678.0), (300.0, 678.0), (300.0, 768.0), (15.0, 768.0)]

    det, engine = _detector_with(cfg, scaled_poly)
    boxes = det.detect(_frame(1080, 1920))

    # 엔진 입력: 밴드 크롭 + 다운스케일이 동시에 적용된 형태
    assert engine.seen_shapes, "engine.predict가 호출되지 않음"
    seen_h, seen_w = engine.seen_shapes[0][:2]
    assert seen_w <= 640
    assert abs(seen_h - 432 * (seen_w / 1920)) <= 1.0

    assert len(boxes) == 1
    assert _pts_close(boxes[0], expected)
    # 복원된 좌표가 원본 프레임 안에 있고, 높이 필터도 복원 기준으로 통과
    assert boxes[0].height >= cfg.min_box_height
    y0 = 1080 * 0.6
    assert all(y0 - 1.0 <= y <= 1080.0 for _, y in boxes[0].pts)


# --- None 설정: 원본 통과 (동작 변화 없음) --------------------------------


def test_none_options_pass_through_unchanged():
    # det_max_width 필드가 생기면 명시적으로 None을 넣고, 없으면 기본 Config
    extra = (
        {"det_max_width": None}
        if "det_max_width" in Config.__dataclass_fields__
        else {}
    )
    cfg = replace(Config(), roi_band=None, **extra)
    poly = [(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]

    det, engine = _detector_with(cfg, poly)
    frame = _frame(360, 640)
    boxes = det.detect(frame)

    # 원본 이미지 그대로 엔진에 전달 (크롭/리사이즈 없음)
    assert engine.seen_shapes == [(360, 640, 3)]

    assert len(boxes) == 1
    assert _pts_close(boxes[0], poly, tol=0.0)
