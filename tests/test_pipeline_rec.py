"""crop 변화 임계값 회귀 테스트 (DEFECT-1 변형, 다른 텍스트 쌍 사용).

공개 동작만 검증한다(내부 RecognitionCoordinator 구조는 리팩터 대상):
- detect는 밴드에 텍스트가 있는 동안 항상 같은 bbox를 반환(위치 불변),
- recognize는 현재 프레임에 렌더된 자막 텍스트를 반환(첫 구간 A, 이후 B).

기대: 기본 Config()에서 crop 내용 변화가 인식되어 이벤트 2개(A, B)로
분리되고, 어느 한쪽 텍스트도 유실되지 않는다.
"""
from __future__ import annotations

from unittest import mock

import cv2
import numpy as np

from fixtures.make_synth_video import make_frame, make_synth
from vte.config import Config
from vte.detector import TextDetector
from vte.models import TextBox
from vte.pipeline import run_extract
from vte.recognizer import Recognizer

_TEXT_A = "오늘 하루도 수고했어"
_TEXT_B = "내일은 더 좋을 거야"

# fixture 영상의 흰 밴드와 일치하는 고정 bbox (하단 밴드)
_BAND_PTS = [(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]

_SIG_SIZE = (64, 16)


def _sig(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, _SIG_SIZE).astype(np.int16)


def _band_has_text(frame) -> bool:
    band = frame[292:350, 20:620]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    return int((gray > 220).sum()) > 1000 and int((gray < 100).sum()) > 100


def test_crop_content_change_splits_into_two_events(tmp_path):
    video = str(tmp_path / "rec_pair.mp4")
    make_synth(video, text1=_TEXT_A, text2=_TEXT_B)

    ref_a = _sig(make_frame(1.0, _TEXT_A, _TEXT_B))
    ref_b = _sig(make_frame(5.0, _TEXT_A, _TEXT_B))
    phase = {"text": ""}

    def fake_detect(self, image):
        if not _band_has_text(image):
            phase["text"] = ""
            return []
        dist_a = float(np.mean(np.abs(_sig(image) - ref_a)))
        dist_b = float(np.mean(np.abs(_sig(image) - ref_b)))
        phase["text"] = _TEXT_A if dist_a <= dist_b else _TEXT_B
        return [TextBox(list(_BAND_PTS), 0.99)]

    def fake_recognize(self, image):
        return (phase["text"], 0.97)

    with mock.patch.object(TextDetector, "detect", fake_detect), mock.patch.object(
        Recognizer, "recognize", fake_recognize
    ):
        events = run_extract(video, Config())

    assert len(events) == 2, f"expected 2 events, got {events}"
    first, second = events
    assert first.text == _TEXT_A
    assert second.text == _TEXT_B
    assert first.start < 4.0
    assert second.start >= 4.0
