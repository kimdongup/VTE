"""미리보기 영상 서빙(Range) 수동 스모크.

    .venv/bin/python tests/smoke_media.py

합성 mp4를 임시로 만들어 /api/media 의 200/206 동작과 Accept-Ranges
헤더를 실제 HTTP로 확인한다. 산출물은 /tmp 에만 남는다.
"""
from __future__ import annotations

import pathlib
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from vte.ui import create_server  # noqa: E402
from vte.ui.app import ExtractionApp  # noqa: E402
from vte.ui.features.media import _parse_range  # noqa: E402


def main() -> int:
    from fixtures.make_synth_video import make_synth

    tmp = pathlib.Path("/tmp/vte_media_smoke.mp4")
    make_synth(str(tmp))
    size = tmp.stat().st_size

    server = create_server(ExtractionApp(), "127.0.0.1", 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = (
        f"http://127.0.0.1:{port}/api/media?path="
        + urllib.parse.quote(str(tmp.resolve()))
    )

    def get(headers=None):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            resp = urllib.request.urlopen(req)
            return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    # 1) 단순 요청 → 200 + Accept-Ranges
    status, headers, body = get()
    assert status == 200, status
    assert headers.get("Accept-Ranges") == "bytes", headers.get("Accept-Ranges")
    assert len(body) == size, (len(body), size)
    print(f"GET full        -> {status}, {len(body)}B, Accept-Ranges={headers.get('Accept-Ranges')}")

    # 2) 부분 요청 → 206 + Content-Range + 정확한 바이트
    status, headers, chunk = get({"Range": "bytes=100-199"})
    assert status == 206, status
    assert headers.get("Content-Range") == f"bytes 100-199/{size}", headers.get("Content-Range")
    assert chunk == tmp.read_bytes()[100:200], "chunk mismatch"
    print(f"GET bytes=100-199 -> {status}, {len(chunk)}B, Content-Range={headers.get('Content-Range')}")

    # 3) 개방형 구간 / suffix 구간
    status, headers, chunk = get({"Range": "bytes=100-"})
    assert status == 206 and len(chunk) == size - 100, (status, len(chunk))
    print(f"GET bytes=100-    -> {status}, {len(chunk)}B")

    status, headers, chunk = get({"Range": "bytes=-64"})
    assert status == 206 and len(chunk) == 64, (status, len(chunk))
    assert headers.get("Content-Range") == f"bytes {size - 64}-{size - 1}/{size}"
    print(f"GET bytes=-64     -> {status}, {len(chunk)}B, Content-Range={headers.get('Content-Range')}")

    # 4) 해석 불가/범위 밖 → 전체 200 (브라우저 호환성)
    for bad in ["bytes=abc", "bytes=99999999-", "garbage", ""]:
        status, _, body = get({"Range": bad})
        assert status == 200 and len(body) == size, (bad, status, len(body))
    print("GET bad ranges    -> 200 (full body fallback)")

    # 5) 확장자 거부 / 누락 / 미존재
    other = pathlib.Path(__file__).resolve()
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/media?path=" + urllib.parse.quote(str(other))
        )
        raise AssertionError("unsupported suffix should be rejected")
    except urllib.error.HTTPError as err:
        assert err.code == 415, err.code
        print("GET .py file      -> 415")

    for query, expect in [("", 400), (f"path={urllib.parse.quote('/no/such.mp4')}", 404)]:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/media?{query}")
            raise AssertionError(f"{query!r} should fail")
        except urllib.error.HTTPError as err:
            assert err.code == expect, (query, err.code)
            print(f"GET {query or '(no path)':<24} -> {err.code}")

    # 6) 파서 단위 경계
    assert _parse_range("bytes=0-1,5-6", 1000) == (0, 1)  # 멀티 레인지는 첫 구간만
    assert _parse_range("bytes=-0", 1000) == (0, 999)
    assert _parse_range("bytes=500-499", 1000) is None  # 역전
    assert _parse_range("bytes=-", 1000) is None
    print("_parse_range edges -> OK")

    server.shutdown()
    server.server_close()
    tmp.unlink(missing_ok=True)
    print("MEDIA SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
