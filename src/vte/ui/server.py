"""Minimal HTTP server core for the VTE web UI.

의존성 최소화를 위해 표준 라이브러리 ``http.server`` 만 사용한다.

구성요소:
- :class:`Router` — 데코레이터 기반 경로 등록. 기능 추가는 라우트 하나.
- :class:`Request` / :class:`Response` — 핸들러가 다루는 단순화된 값 객체.
- :func:`create_server` — 정적 파일 + 등록된 라우트를 서빙하는 ThreadingHTTPServer.
- SSE 응답은 :class:`SSEStream` 이 특별 응답 타입으로 취급된다.
"""

from __future__ import annotations

import json
import mimetypes
import re
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None


@dataclass
class Response:
    status: int = 200
    body: bytes = b""
    content_type: str = "application/json; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, obj: Any, status: int = 200) -> "Response":
        return cls(status=status, body=json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    @classmethod
    def error(cls, status: int, message: str) -> "Response":
        return cls.from_json({"error": message}, status=status)


@dataclass
class SSEStream:
    """SSE 응답: ``events`` 제너레이터의 각 항목을 ``data: ...`` 블록으로 보낸다."""

    events: Callable[[], Iterator[tuple[str, Any]]]
    retry_ms: int = 2000


Handler = Callable[[Request], Response | SSEStream]
Route = tuple[str, re.Pattern[str], Handler]


class Router:
    """경로 패턴 → 핸들러 매핑. 기능 모듈이 register() 안에서 사용한다."""

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def _add(self, method: str, pattern: str, handler: Handler) -> Handler:
        # ``/api/jobs/{id}`` 같은 템플릿 경로를 정규식 캡처로 변환한다.
        regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)
        self._routes.append((method.upper(), re.compile(f"^{regex}$"), handler))
        return handler

    def get(self, pattern: str) -> Callable[[Handler], Handler]:
        def wrap(handler: Handler) -> Handler:
            return self._add("GET", pattern, handler)
        return wrap

    def post(self, pattern: str) -> Callable[[Handler], Handler]:
        def wrap(handler: Handler) -> Handler:
            return self._add("POST", pattern, handler)
        return wrap

    def dispatch(self, req: Request) -> Response | SSEStream | None:
        path_matched = False
        for method, regex, handler in self._routes:
            match = regex.match(req.path)
            if not match:
                continue
            path_matched = True
            if method != req.method.upper():
                continue
            result = handler(req)
            if isinstance(result, (Response, SSEStream)):
                return result
            raise TypeError(f"handler for {req.path} returned {type(result)!r}")
        if path_matched:
            return Response.error(405, "method not allowed")
        return None


class _Handler(BaseHTTPRequestHandler):
    """라우터 + 정적 파일 + SSE를 서빙하는 핸들러."""

    server_version = "VTE-UI/0.1"
    protocol_version = "HTTP/1.1"

    # 주입될 속성 (create_server에서 설정)
    router: Router
    static_dir: Path

    def log_message(self, fmt: str, *args: Any) -> None:  # 기본 로그 조용히
        pass

    def _respond(self, resp: Response) -> None:
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(resp.body)))
        for key, value in resp.headers.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(resp.body)

    def _respond_sse(self, stream: SSEStream) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(f"retry: {stream.retry_ms}\n\n".encode())
        try:
            for kind, payload in stream.events():
                data = json.dumps({"type": kind, **payload}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # 클라이언트가 닫음

    def _serve_static(self, path: str) -> Response:
        rel = path.lstrip("/") or "index.html"
        target = (self.static_dir / rel).resolve()
        try:
            target.relative_to(self.static_dir.resolve())
        except ValueError:
            return Response.error(403, "forbidden")
        if not target.is_file():
            return Response.error(404, "not found")
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        return Response(status=200, body=target.read_bytes(), content_type=ctype)

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        req = Request(
            method=self.command,
            path=parsed.path,
            query=query,
            body=body,
            headers={k.lower(): v for k, v in self.headers.items()},
        )
        resp = self.router.dispatch(req)
        if resp is None:
            resp = self._serve_static(parsed.path)
        if isinstance(resp, SSEStream):  # 라우트 핸들러가 SSE를 반환한 경우
            self._respond_sse(resp)
            return
        self._respond(resp)

    do_GET = do_POST = do_HEAD = _handle


def create_server(
    app: "ExtractionApp",
    host: str = "127.0.0.1",
    port: int = 8765,
    static_dir: Path | None = None,
) -> ThreadingHTTPServer:
    """라우트(feature 모듈들)를 등록하고 서버 인스턴스를 만든다.

    ``port=0`` 이면 임의의 빈 포트를 배정한다(테스트용).
    """
    from .features import register_all

    router = Router()
    register_all(router, app)

    handler_cls = type(
        "BoundHandler",
        (_Handler,),
        {"router": router, "static_dir": Path(static_dir or STATIC_DIR)},
    )
    server = ThreadingHTTPServer((host, port), handler_cls)
    server.daemon_threads = True
    return server


def run_ui(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """UI 서버를 시작하고 (선택적으로) 기본 브라우저를 연다. Ctrl-C로 종료."""
    import webbrowser

    from .app import ExtractionApp

    app = ExtractionApp()
    server = create_server(app, host, port)
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"VTE UI running at {url}  (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down VTE UI...")
    finally:
        server.shutdown()
        server.server_close()


