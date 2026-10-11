"""UI 백엔드(잡·라우트·SSE) 테스트 — OCR 엔진 없이 검증.

파이프라인은 mock extract_fn으로 주입하고, HTTP 라우트는 인메모리 서버로
검사한다. 프론트엔드(JS)는 브라우저 필요하므로 별도 스모크로 분리(tests/smoke_ui.py).
"""
from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

import pytest

from vte.config import Config
from vte.detector import TextDetector
from vte.models import TextBox, TextEvent
from vte.pipeline import ProgressUpdate, run_extract
from vte.recognizer import Recognizer
from vte.ui import ExtractionApp, create_server
from vte.ui.app import ExtractionJob, JobRunningError

# fixture 영상의 흰 밴드 bbox (test_integration과 동일)
_BAND_PTS = [(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]


def _events():
    return [
        TextEvent(0.0, 3.0, "첫번째 자막", [TextBox(list(_BAND_PTS), 0.98)], 0.98),
        TextEvent(4.0, 7.0, "두번째 자막", [TextBox(list(_BAND_PTS), 0.97)], 0.97),
    ]


def _fake_extract(video, cfg, start=0.0, end=None, on_progress=None, should_stop=None):
    """진행 이벤트를 하나 방송하고 이벤트를 반환하는 파이프라인 대체물."""
    if on_progress:
        on_progress(
            type("U", (), {
                "ts": 1.5, "duration": 8.0, "frame_idx": 3, "processed": True,
                "detections": [[(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]],
                "active": [{"id": 1, "text": "첫번째 자막", "start": 0.0, "end": 3.0,
                            "rect": [40.0, 300.0, 600.0, 346.0]}],
                "closed": [],
            })()
        )
    return _events()


# ---- 잡 단위 -------------------------------------------------------------


def test_job_publishes_progress_and_done():
    job = ExtractionJob("fake.mp4", mode="fast", extract_fn=_fake_extract)
    q = job.subscribe()
    job.start()
    job.wait(timeout=5)

    seen = []
    while not q.empty():
        seen.append(q.get_nowait())
    kinds = [k for k, _ in seen]
    assert "snapshot" in kinds and "progress" in kinds and "done" in kinds
    snap = job.snapshot()
    assert snap.state == "done"
    assert [e["text"] for e in snap.events] == ["첫번째 자막", "두번째 자막"]


def test_job_error_state():
    def boom(*a, **k):
        raise RuntimeError("실패")

    job = ExtractionJob("fake.mp4", extract_fn=boom)
    job.start()
    job.wait(timeout=5)
    snap = job.snapshot()
    assert snap.state == "error"
    assert "실패" in snap.error


def test_app_rejects_second_job_while_running():
    import threading

    release = threading.Event()

    def slow(video, cfg, start=0.0, end=None, on_progress=None, should_stop=None):
        release.wait(timeout=5)
        return []

    app = ExtractionApp()
    # 실행 중인 잡을 배치 (start_job 경유 없이 주입)
    job = ExtractionJob("fake.mp4", extract_fn=slow)
    app._job = job
    job.start()
    try:
        with pytest.raises(JobRunningError):
            app.start_job("another.mp4")
    finally:
        release.set()
        job.wait(timeout=5)


# ---- HTTP 라우트 ---------------------------------------------------------


@pytest.fixture
def live_server():
    app = ExtractionApp()
    server = create_server(app, port=0)
    import threading

    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield app, base
    server.shutdown()
    server.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, r.read()


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


def test_http_status_and_static(live_server):
    app, base = live_server
    s, body = _get(base, "/api/status")
    assert s == 200 and json.loads(body) == {"job": None}
    s, body = _get(base, "/")
    assert s == 200 and b"VTE" in body


def test_http_extract_validation(live_server):
    app, base = live_server
    with pytest.raises(urllib.error.HTTPError) as ei:
        _post(base, "/api/extract", {})
    assert ei.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as ei:
        _post(base, "/api/extract", {"video": "x.mp4", "mode": "bogus"})
    assert ei.value.code == 400


def test_http_export_requires_done_job(live_server):
    app, base = live_server
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get(base, "/api/export?format=srt")
    assert ei.value.code == 409


def test_http_export_after_done(live_server):
    app, base = live_server
    # 완료된 잡을 직접 배치
    job = ExtractionJob("fake.mp4", extract_fn=_fake_extract)
    app._job = job
    job.start()
    job.wait(timeout=5)
    s, body = _get(base, "/api/export?format=srt")
    assert s == 200
    text = body.decode("utf-8")
    assert "첫번째 자막" in text and "00:00:00,000" in text


def test_http_export_bad_format(live_server):
    app, base = live_server
    job = ExtractionJob("fake.mp4", extract_fn=_fake_extract)
    app._job = job
    job.start()
    job.wait(timeout=5)
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get(base, "/api/export?format=bogus")
    assert ei.value.code == 400


# ---- 파이프라인 진행 콜백 (합성 영상 + mock OCR) --------------------------


def test_run_extract_emits_progress(synth_video):
    """on_progress가 샘플마다 호출되고, 구조가 채워지는지 검증."""
    updates: list[ProgressUpdate] = []

    def fake_detect(self, image):
        band = image[292:350, 20:620]
        import cv2
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        if int((gray > 220).sum()) > 1000 and int((gray < 100).sum()) > 100:
            return [TextBox(list(_BAND_PTS), 0.99)]
        return []

    with mock.patch.object(TextDetector, "detect", fake_detect), mock.patch.object(
        Recognizer, "recognize", lambda self, img: ("첫번째 자막", 0.98)
    ):
        events = run_extract(synth_video, Config(), on_progress=updates.append)

    assert updates, "on_progress가 호출되지 않음"
    ts_list = [u.ts for u in updates]
    assert ts_list == sorted(ts_list)  # 단조 증가
    assert all(u.duration > 0 for u in updates)
    first_processed = next(u for u in updates if u.processed)
    assert first_processed.detections, "processed 샘플에 detections가 없음"
    assert isinstance(first_processed.active, list)
    assert isinstance(first_processed.closed, list)
    assert events  # 최종 결과도 기존과 동일하게 반환


def test_run_extract_should_stop_short_circuits(synth_video):
    """should_stop이 True를 반환하면 즉시 종료하고 부분 결과를 반환한다."""
    calls = {"n": 0}

    def stop_after_two():
        calls["n"] += 1
        return calls["n"] > 2

    def fake_detect(self, image):
        return [TextBox(list(_BAND_PTS), 0.99)]

    with mock.patch.object(TextDetector, "detect", fake_detect), mock.patch.object(
        Recognizer, "recognize", lambda self, img: ("첫번째 자막", 0.98)
    ):
        events = run_extract(synth_video, Config(), should_stop=stop_after_two)

    assert calls["n"] <= 3  # 전체 영상을 다 돌지 않음
    assert isinstance(events, list)


def test_run_extract_no_callbacks_unchanged(synth_video):
    """콜백 없이 기존과 동일하게 동작하는지 회귀 확인."""
    def fake_detect(self, image):
        band = image[292:350, 20:620]
        import cv2
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        if int((gray > 220).sum()) > 1000 and int((gray < 100).sum()) > 100:
            return [TextBox(list(_BAND_PTS), 0.99)]
        return []

    with mock.patch.object(TextDetector, "detect", fake_detect), mock.patch.object(
        Recognizer, "recognize", lambda self, img: ("첫번째 자막", 0.98)
    ):
        events = run_extract(synth_video, Config())
    assert isinstance(events, list) and events


def test_job_end_to_end_with_real_pipeline(synth_video):
    """실제 파이프라인(mock OCR)을 잡으로 돌려 SSE 페이로드 형태를 검증.

    프론트엔드가 progress 이벤트에서 기대하는 필드(ts, duration, detections,
    active, closed)가 모두 있고, done 이벤트에 최종 텍스트가 오는지 확인한다.
    """
    def fake_detect(self, image):
        band = image[292:350, 20:620]
        import cv2
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        if int((gray > 220).sum()) > 1000 and int((gray < 100).sum()) > 100:
            return [TextBox(list(_BAND_PTS), 0.99)]
        return []

    app = ExtractionApp()
    with mock.patch.object(TextDetector, "detect", fake_detect), mock.patch.object(
        Recognizer, "recognize", lambda self, img: ("첫번째 자막", 0.98)
    ):
        job = app.start_job(synth_video, mode="fast")
        q = job.subscribe()
        job.wait(timeout=30)

    snap = job.snapshot()
    assert snap.state == "done", snap.error
    # done 이벤트에 텍스트가 있어야 프론트 하단 목록이 채워진다
    assert snap.events and snap.events[0]["text"] == "첫번째 자막"

    # 구독 채널에서 progress 페이로드 형태 검증
    kinds = []
    while not q.empty():
        kinds.append(q.get_nowait())
    progress_payloads = [p for k, p in kinds if k == "progress"]
    assert progress_payloads, "progress 이벤트가 없음"
    p0 = progress_payloads[-1]
    for field in ("ts", "duration", "frame_idx", "processed", "detections", "active", "closed"):
        assert field in p0, f"progress 필드 누락: {field}"
    assert isinstance(p0["detections"], list)
    assert all(isinstance(pt, list) and len(pt) == 2 for box in p0["detections"] for pt in box)

# ---- 미디어 서빙 (Range) --------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get_raw(base, path, headers=None):
    """리다이렉트·재시도 없이 원문 응답(상태/헤더/본문)을 받는다."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(base + path, headers=headers or {})
    try:
        with opener.open(req, timeout=5) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def _media_url(video):
    """pathlib.Path 를 받아 /api/media 쿼리를 만든다."""
    return f"/api/media?path={urllib.parse.quote(str(pathlib.Path(video).resolve()))}"


def test_media_full_response_advertises_ranges(live_server, synth_video):
    """Range 없이 전체 요청이면 200 + Accept-Ranges 헤더를 준다."""
    video = pathlib.Path(synth_video)  # fixture는 str 경로를 준다
    _, base = live_server
    status, headers, body = _get_raw(base, _media_url(video))
    assert status == 200, status
    assert headers.get("Accept-Ranges") == "bytes"
    assert len(body) == video.stat().st_size


def test_media_serves_partial_content(live_server, synth_video):
    """<video> 탐색에 필요한 206 부분 응답과 정확한 바이트 범위를 검증."""
    video = pathlib.Path(synth_video)
    _, base = live_server
    size = video.stat().st_size
    status, headers, chunk = _get_raw(base, _media_url(video), {"Range": "bytes=100-199"})
    assert status == 206, status
    assert headers.get("Content-Range") == f"bytes 100-199/{size}"
    assert chunk == video.read_bytes()[100:200]


def test_media_open_ended_and_suffix_ranges(live_server, synth_video):
    """개방형(bytes=100-)과 suffix(bytes=-64) 구간도 206으로 처리한다."""
    video = pathlib.Path(synth_video)
    _, base = live_server
    size = video.stat().st_size
    url = _media_url(video)

    status, _, chunk = _get_raw(base, url, {"Range": "bytes=100-"})
    assert status == 206 and len(chunk) == size - 100

    status, headers, chunk = _get_raw(base, url, {"Range": "bytes=-64"})
    assert status == 206 and len(chunk) == 64
    assert headers.get("Content-Range") == f"bytes {size - 64}-{size - 1}/{size}"


@pytest.mark.parametrize("bad", ["bytes=abc", "bytes=99999999-", "garbage", ""])
def test_media_unparsable_range_falls_back_to_full(live_server, synth_video, bad):
    """해석 불가/범위 밖 Range는 전체 200으로 응답해 브라우저 호환성을 유지."""
    video = pathlib.Path(synth_video)
    _, base = live_server
    status, _, body = _get_raw(base, _media_url(video), {"Range": bad})
    assert status == 200, (bad, status)
    assert len(body) == video.stat().st_size


def test_media_rejects_non_video_and_missing(live_server):
    """영상 외 확장자/누락/미존재 경로는 각각 415/400/404."""
    _, base = live_server

    with pytest.raises(urllib.error.HTTPError) as e1:
        urllib.request.urlopen(
            f"{base}/api/media?path={urllib.parse.quote(str(pathlib.Path(__file__).resolve()))}",
            timeout=5,
        )
    assert e1.value.code == 415

    with pytest.raises(urllib.error.HTTPError) as e2:
        urllib.request.urlopen(f"{base}/api/media", timeout=5)
    assert e2.value.code == 400

    with pytest.raises(urllib.error.HTTPError) as e3:
        urllib.request.urlopen(f"{base}/api/media?path=%2Fno%2Fsuch.mp4", timeout=5)
    assert e3.value.code == 404


@pytest.mark.parametrize(
    "header,size,expected",
    [
        ("bytes=0-99", 1000, (0, 99)),
        ("bytes=100-", 1000, (100, 999)),
        ("bytes=-128", 1000, (872, 999)),
        ("bytes=0-0", 10, (0, 0)),
        ("bytes=0-1,5-6", 1000, (0, 1)),  # 멀티 레인지는 첫 구간만
        ("bytes=500-499", 1000, None),  # 역전
        ("bytes=2000-3000", 1000, None),  # 시작이 size 밖
        ("bytes=-", 1000, None),
        ("bytes=abc", 1000, None),
        ("garbage", 1000, None),
        ("", 1000, None),
    ],
)
def test_parse_range(header, size, expected):
    from vte.ui.features.media import _parse_range

    assert _parse_range(header, size) == expected

