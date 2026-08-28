"""실영상(첫 60초) 골든 JSON 검사.

golden 파일은 pytest에서 생성하지 않고 ``tests/golden/capture_golden.py``를
1회 수동 실행해 만든다 (실엔진 full pipeline은 수 분 소요).

- 구조 검사: golden이 있으면 항상 수행 (빠름).
- 현재 파이프라인과의 비교: 실엔진 재실행이 필요해 느리므로
  ``VTE_GOLDEN_LIVE=1`` 환경변수가 있을 때만 실행한다. 판정 기준:
  이벤트 start/end ±1.0초, 텍스트 rapidfuzz ratio ≥ 80.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from rapidfuzz import fuzz

from vte.config import Config
from vte.pipeline import run_extract

GOLDEN = Path(__file__).parent / "golden" / "first60s.json"
ROOT_DIR = Path(__file__).resolve().parents[1]
_LOCAL_VIDEO = ROOT_DIR / "claude_first60s.mp4"
_FALLBACK_VIDEO = Path("/Users/mac/Downloads/my_training/claude_first60s.mp4")
VIDEO = _LOCAL_VIDEO if _LOCAL_VIDEO.exists() else _FALLBACK_VIDEO

TIME_TOL = 1.0
TEXT_RATIO_MIN = 80.0


def _load_golden() -> dict:
    if not GOLDEN.exists():
        pytest.skip(
            "golden 파일 없음: .venv/bin/python tests/golden/capture_golden.py 실행"
        )
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_golden_schema():
    data = _load_golden()
    assert set(data) == {"meta", "events"}

    meta = data["meta"]
    assert meta["mode"] == "fast"
    assert meta["det_model"] and meta["rec_model"]
    assert "created" in meta

    events = data["events"]
    assert events, "골든 이벤트가 비어 있음"

    prev_start = -1.0
    for ev in events:
        assert set(ev) == {"start", "end", "text", "confidence", "bboxes"}
        assert 0.0 <= ev["start"] < ev["end"] <= 65.0
        assert isinstance(ev["text"], str) and ev["text"]
        assert 0.0 <= ev["confidence"] <= 1.0
        # bboxes는 polygon 점 [x, y] 쌍의 리스트 (한 박스 = 4점 이상)
        assert len(ev["bboxes"]) >= 4
        for pt in ev["bboxes"]:
            assert len(pt) == 2 and all(isinstance(v, float) for v in pt)
        assert ev["start"] >= prev_start - 1e-9  # 시작 시각 정렬 유지
        prev_start = ev["start"]


def test_golden_matches_current_pipeline():
    if os.environ.get("VTE_GOLDEN_LIVE") != "1":
        pytest.skip("실엔진 재실행 비교는 VTE_GOLDEN_LIVE=1일 때만 (수 분 소요)")
    if not VIDEO.exists():
        pytest.skip(f"샘플 영상 없음: {VIDEO}")

    golden_events = _load_golden()["events"]
    current = sorted(run_extract(str(VIDEO), Config.for_mode("fast")), key=lambda e: e.start)

    matched: set[int] = set()
    for g in golden_events:
        best_i, best_key = None, None
        for i, c in enumerate(current):
            if i in matched:
                continue
            key = abs(c.start - g["start"]) + abs(c.end - g["end"])
            if best_key is None or key < best_key:
                best_i, best_key = i, key
        assert best_i is not None, f"비교 대상 이벤트 부족: golden={g['text']!r}"
        c = current[best_i]
        assert abs(c.start - g["start"]) <= TIME_TOL, (
            f"start 불일치: golden={g['start']} current={c.start} ({g['text']!r})"
        )
        assert abs(c.end - g["end"]) <= TIME_TOL, (
            f"end 불일치: golden={g['end']} current={c.end} ({g['text']!r})"
        )
        ratio = fuzz.ratio(g["text"], c.text)
        assert ratio >= TEXT_RATIO_MIN, (
            f"텍스트 불일치(ratio={ratio:.1f}): golden={g['text']!r} "
            f"current={c.text!r}"
        )
        matched.add(best_i)
