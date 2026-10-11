"""결과 내보내기 라우트.

GET /api/export?format=srt|txt|json|ass — 완료된 잡의 이벤트를 텍스트로 변환.
아직 잡이 끝나지 않았으면 409를 반환한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...exporter import FORMATS, export
from ...models import TextEvent
from ..server import Request, Response

if TYPE_CHECKING:
    from ..app import ExtractionApp
    from ..server import Router


def _to_events(raw: list[dict]) -> list[TextEvent]:
    return [
        TextEvent(start=e["start"], end=e["end"], text=e["text"], confidence=e["confidence"])
        for e in raw
    ]


def register(router: "Router", app: "ExtractionApp") -> None:
    @router.get("/api/export")
    def export_result(req: Request) -> Response:
        fmt = req.query.get("format", "srt")
        if fmt not in FORMATS:
            return Response.error(400, f"unknown format: {fmt!r} (choose from {sorted(FORMATS)})")
        job = app.job
        if job is None:
            return Response.error(409, "no job yet")
        snap = job.snapshot()
        if snap.state == "running":
            return Response.error(409, "job still running")
        if snap.state == "error":
            return Response.error(409, f"job failed: {snap.error}")
        text = export(_to_events(snap.events or []), fmt)
        return Response(
            status=200,
            body=text.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="vte_output.{fmt}"'},
        )
