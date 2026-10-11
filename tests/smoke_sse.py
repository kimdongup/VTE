"""SSE 응답과 정적 리소스 MIME 타입을 직접 검사하는 수동 확인 스크립트.

실행: .venv/bin/python tests/smoke_sse.py
"""
import http.client
import threading
import urllib.request

from vte.ui import ExtractionApp, create_server

PATHS = [
    "/", "/css/app.css", "/js/app.js", "/js/core/api.js", "/js/core/registry.js",
    "/js/panels/controls.js", "/js/panels/preview.js", "/js/panels/transcript.js",
    "/js/panels/exporter.js",
]


def main():
    app = ExtractionApp()
    server = create_server(app, port=0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    for path in PATHS:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            print(f"{path:34s} {r.status} {r.headers.get('Content-Type')}")

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request("GET", "/api/events")
    r = conn.getresponse()
    print("SSE status:", r.status, r.getheader("Content-Type"))
    line = r.fp.readline().decode()
    print("SSE first line:", repr(line))
    conn.close()
    server.shutdown()
    print("FULL SMOKE OK")


if __name__ == "__main__":
    main()
