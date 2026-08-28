"""DEFECT-1 회귀 테스트: 동일 위치 연속 자막의 텍스트 유실.

기존 test_integration.py와 달리 scene_threshold 우회(-1.0)를 쓰지 않고
기본 Config()로 실행한다. detect는 합성 영상 하단 밴드에 텍스트가 있을 때
항상 동일한 bbox를 반환하고(= 위치만으로는 구분 불가능한 시나리오),
recognize는 트랙 종료 순서대로 두 자막 텍스트를 반환한다.

기대: 이벤트 2개, 텍스트 각각 일치.
"""
from __future__ import annotations

from unittest import mock

import cv2
import pytest

from vte.config import Config
from vte.detector import TextDetector
from vte.models import TextBox
from vte.pipeline import run_extract
from vte.recognizer import Recognizer

_SUB1 = "첫번째 자막"
_SUB2 = "두번째 자막"

# fixture 영상의 흰 밴드와 일치하는 고정 bbox (하단 밴드)
_BAND_PTS = [(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]


def _band_has_text(frame) -> bool:
    """하단 밴드에 흰 배경 + 어두운 금서가 함께 있으면 True."""
    band = frame[292:350, 20:620]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    return int((gray > 220).sum()) > 1000 and int((gray < 100).sum()) > 100


def _fake_detect(self, image):
    if _band_has_text(image):
        return [TextBox(list(_BAND_PTS), 0.99)]
    return []


def test_same_position_consecutive_subtitles_not_merged(synth_video):
    texts = iter([_SUB1, _SUB2])

    with mock.patch.object(TextDetector, "detect", _fake_detect), mock.patch.object(
        Recognizer, "recognize", lambda self, image: (next(texts), 0.98)
    ):
        events = run_extract(synth_video, Config())

    assert len(events) == 2, f"expected 2 events, got {events}"
    assert events[0].text == _SUB1
    assert events[1].text == _SUB2
