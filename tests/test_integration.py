"""파이프라인 통합 테스트 (OCR 엔진은 mock, 나머지는 실제 로직).

VideoReader -> SceneDetector -> Tracker -> Segmenter -> Exporter 전체가
실제로 동작하고, 느린 PaddleOCR 경계(TextDetector.detect /
Recognizer.recognize)만 mock으로 교체한다.

참고: Recognizer.recognize는 이제 트랙당 1회가 아니라 **crop 내용 변화당**
호출되는 것이 pipeline 규약이다. 따라서 mock은 호출 순서에 의존하지 않고,
합성 프레임을 직접 렌더링해 만든 기준 시그니처와의 픽셀 거리로 crop 내용이
어느 자막인지 판정한다(_ContentMappedTexts).

참고: 정적 스킵 동작 자체는 test_scene_detector.py에서 단위 검증되며,
여기서는 기본 Config()(scene_threshold=0.12)를 그대로 사용한다. 자막이
바뀌는 순간(3~4초 경계) 프레임이 변해 샘플이 처리되므로 우회 설정이
필요 없다.
"""
from __future__ import annotations

import json
from unittest import mock

import cv2
import numpy as np

from vte.config import Config
from vte.detector import TextDetector
from vte.exporter import export
from vte.models import TextBox
from vte.pipeline import run_extract
from vte.preprocess import crop_box, enhance
from vte.recognizer import Recognizer

_SUB1 = "첫번째 자막"
_SUB2 = "두번째 자막"

# fixture 영상의 흰 밴드와 일치하는 고정 bbox (하단 밴드)
_BAND_PTS = [(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]

_SIG_SIZE = (128, 32)


def _sig(image: np.ndarray) -> np.ndarray:
    """recognize 입력 이미지의 축소 회색 시그니처."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, _SIG_SIZE).astype(np.int16)


def _ref_sig(t: float) -> np.ndarray:
    """시각 ``t``의 합성 프레임에서 pipeline과 동일하게 crop+enhance한 시그니처."""
    from fixtures.make_synth_video import make_frame

    crop = crop_box(make_frame(t), _BAND_PTS)
    return _sig(enhance(crop))


class _ContentMappedTexts:
    """crop 내용 기준 매핑 recognize mock (호출 순서 비의존)."""

    def __init__(self) -> None:
        self._refs = [(_ref_sig(1.0), _SUB1), (_ref_sig(5.0), _SUB2)]

    def __call__(self, image):
        sig = _sig(image)
        text, best = None, float("inf")
        for ref, candidate in self._refs:
            dist = float(np.mean(np.abs(sig - ref)))
            if dist < best:
                text, best = candidate, dist
        return text, 0.98


def _band_has_text(frame) -> bool:
    """프레임 하단에 흰 밴드(밝은 픽셀)와 글씨(어두운 픽셀)가 함께 있으면 True."""
    band = frame[292:350, 20:620]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    bright = int((gray > 220).sum())
    dark = int((gray < 100).sum())
    return bright > 1000 and dark > 100


def _fake_detect(self, image):
    if _band_has_text(image):
        return [TextBox(list(_BAND_PTS), 0.99)]
    return []


def test_extract_two_subtitle_events(synth_video):
    """자막 2구간 -> 정확히 2개 이벤트, 텍스트·시작시각 검증 (기본 Config)."""
    cfg = Config()

    with mock.patch.object(TextDetector, "detect", _fake_detect), mock.patch.object(
        Recognizer, "recognize", _ContentMappedTexts()
    ):
        events = run_extract(synth_video, cfg)

    assert len(events) == 2, f"expected 2 events, got {events}"

    first, second = events
    assert first.text == _SUB1
    assert second.text == _SUB2
    assert first.start < 4.0
    assert second.start >= 4.0
    assert first.end <= 4.0 + 1e-6 or first.end < second.start


def test_extract_json_export_structure(synth_video):
    """JSON export가 파싱 가능한 구조(start/end/text/confidence/bboxes)인지."""
    cfg = Config()

    with mock.patch.object(TextDetector, "detect", _fake_detect), mock.patch.object(
        Recognizer, "recognize", _ContentMappedTexts()
    ):
        events = run_extract(synth_video, cfg)

    payload = json.loads(export(events, "json"))
    assert isinstance(payload, list) and len(payload) == 2
    for item in payload:
        assert set(item) == {"start", "end", "text", "confidence", "bboxes"}
        assert isinstance(item["text"], str) and item["text"]
        assert 0.0 <= item["confidence"] <= 1.0
        assert item["start"] < item["end"]
        for x, y in item["bboxes"]:
            assert isinstance(x, float) and 0.0 <= x <= 640.0
            assert isinstance(y, float) and 0.0 <= y <= 360.0
