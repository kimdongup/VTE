"""UI 서버 스모크 테스트 — HTTP 엔드포인트 동작 검증 (파이프라인 mock).

실행: .venv/bin/python tests/smoke_ui.py
"""

import json
import threading
import urllib.error
import urllib.request

from vte.ui import ExtractionApp, create_server


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, r.read()


def post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


def expect_error(base, path, code_want, payload=None):
    try:
        if payload is not None:
            post(base, path, payload)
        else:
            get(base, path)
    except urllib.error.HTTPError as e:
        assert e.code == code_want, f"{path}: got {e.code}, want {code_want}"
        return e.code
    raise AssertionError(f"{path}: expected HTTP {code_want}, got success")


def main():
    app = ExtractionApp()
    server = create_server(app, port=0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    s, body = get(base, "/")
    assert s == 200 and b"VTE" in body, "index not served"
    print("GET / ->", s, len(body), "bytes")

    s, body = get(base, "/css/app.css")
    assert s == 200 and b"--accent" in body
    print("GET /css/app.css ->", s)

    s, body = get(base, "/js/app.js")
    assert s == 200 and b"App.register" in body
    print("GET /js/app.js ->", s)

    s, body = get(base, "/api/status")
    assert s == 200 and json.loads(body) == {"job": None}
    print("GET /api/status ->", s, "(no job)")

    s = expect_error(base, "/api/extract", 400, {})
    print("POST /api/extract (no video) ->", s)

    s = expect_error(base, "/api/export?format=srt", 409)
    print("GET /api/export (no job) ->", s)

    s = expect_error(base, "/api/media?path=/no/such.mp4", 404)
    print("GET /api/media (missing) ->", s)

    # 존재하지 않는 영상: 잡이 시작(202) 후 오류 상태로 전환되어야 한다.
    s, body = post(base, "/api/extract", {"video": "/no/such.mp4", "mode": "fast"})
    assert s == 202 and body["job"]["id"]
    print("POST /api/extract ->", s, "job", body["job"]["id"])

    # 잡 스레드가 FileNotFoundError로 빠르게 실패하므로 폴링으로 확인.
    import time

    state = None
    for _ in range(50):
        _, raw = get(base, "/api/status")
        body = json.loads(raw)
        state = body["job"]["state"]
        if state in ("error", "done"):
            break
        time.sleep(0.1)
    assert state == "error", f"expected job error state, got {state}"
    print("job reached state:", state, "-", body["job"]["error"])

    server.shutdown()
    print("SMOKE OK")


if __name__ == "__main__":
    main()
