"""영상 파일 서빙 라우트 (미리보기용).

GET /api/media?path=<abs> — 로컬 영상 파일을 바이트로 서빙한다.
브라우저 <video> 태크가 이 경로를 참조한다. 이 UI는 127.0.0.1 전용 로컬
도구이므로 경로 기반 접근을 허용한다.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from ..server import Request, Response

if TYPE_CHECKING:
    from ..app import ExtractionApp
    from ..server import Router

_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def _parse_range(header: str, size: int) -> tuple[int, int] | None:
    """``Range: bytes=start-end`` 한 줄을 파싱해 (start, end) 포함 구간을 돌린다.

    해석 불가·역전·size 밖이면 None (→ 전체 200 응답).
    멀티 레인지(``bytes=0-1,5-6``)는 지원하지 않는다: 브라우저 미디어 요청은
    단일 구간이므로 굳이 처리하지 않는다.
    """
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes="):].split(",")[0].strip()
    if "-" not in spec:
        return None
    raw_start, _, raw_end = spec.partition("-")
    try:
        if not raw_start:  # bytes=-N → 마지막 N바이트
            if not raw_end:
                return None
            length = min(int(raw_end), size)
            return (size - length, size - 1) if length else (0, size - 1)
        start = int(raw_start)
        if start >= size:
            return None
        end = int(raw_end) if raw_end else size - 1
        end = min(end, size - 1)
        return (start, end) if start <= end else None
    except ValueError:
        return None


def register(router: "Router", app: "ExtractionApp") -> None:
    @router.get("/api/media")
    def media(req: Request) -> Response:
        raw = req.query.get("path")
        if not raw:
            return Response.error(400, "path query is required")
        path = Path(raw).expanduser()
        if not path.is_file():
            return Response.error(404, f"file not found: {path}")
        if path.suffix.lower() not in _VIDEO_SUFFIXES:
            return Response.error(415, f"unsupported video type: {path.suffix}")
        ctype = mimetypes.guess_type(str(path))[0] or "video/mp4"
        size = path.stat().st_size
        # <video> 탐색은 Range 요청(206)으로만 즉각 반응한다. 미지원이면
        # 브라우저가 파일을 끝까지 받은 뒤에야 seek가 가능하다.
        common = {"Accept-Ranges": "bytes"}
        span = _parse_range(req.headers.get("range", ""), size)
        if span is None:
            body = path.read_bytes()
            return Response(status=200, body=body, content_type=ctype, headers=common)
        start, end = span
        with path.open("rb") as fh:
            fh.seek(start)
            chunk = fh.read(end - start + 1)
        return Response(
            status=206,
            body=chunk,
            content_type=ctype,
            headers={**common, "Content-Range": f"bytes {start}-{end}/{size}"},
        )
