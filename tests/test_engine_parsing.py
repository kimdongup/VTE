"""실 PaddleOCR 엔진 회귀 테스트.

주의: 느린 테스트입니다. 엔진 초기화와 추론에 수 초~수십 초가 걸리므로
전체 스위트 실행 시간이 크게 늘어날 수 있습니다.

검출/인식 품질이 아니라 엔진 인터페이스 계약(예외 없음, 반환 타입)만 확인한다:
- TextDetector.detect -> list[TextBox] (개수 >= 0, pts는 float 쌍)
- Recognizer.recognize -> (str, float) 튜플
"""
from __future__ import annotations

import pytest

pytest.importorskip("paddleocr")

import sys
from pathlib import Path

# fixtures 모듈 임포트 보장 (conftest가 이미 처리하지만 단독 실행 대비)
sys.path.insert(0, str(Path(__file__).parent))

from fixtures.make_synth_video import make_frame

from vte.config import Config
from vte.detector import TextDetector
from vte.recognizer import Recognizer


@pytest.fixture(scope="module")
def engines():
    cfg = Config()
    return TextDetector(cfg), Recognizer(cfg)


def test_detector_and_recognizer_contract(engines):
    det, rec = engines
    frame = make_frame(0.5)  # "첫번째 자막"이 보이는 프레임

    boxes = det.detect(frame)
    assert isinstance(boxes, list)
    assert len(boxes) >= 0
    for box in boxes:
        for x, y in box.pts:
            assert isinstance(x, float)
            assert isinstance(y, float)

    crop = frame[280:360, :]
    text, score = rec.recognize(crop)
    assert isinstance(text, str)
    assert isinstance(score, float)
    assert score >= 0.0
