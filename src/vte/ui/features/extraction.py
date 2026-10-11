"""추출 시작/상태/취소 라우트.

POST /api/extract   — 새 추출 잡 시작 (실행 중이면 409)
GET  /api/status    — 현재 잡 스냅샷
POST /api/cancel    — 실행 중인 잡 취소
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..app import JobRunningError
from ..server import Request, Response

if TYPE_CHECKING:
    from ..app import ExtractionApp
    from ..server import Router


def register(router: "Router", app: "ExtractionApp") -> None:
    @router.post("/api/extract")
    def start_extract(req: Request) -> Response:
        payload: dict[str, Any] = req.json() or {}
        video = payload.get("video")
        if not video or not isinstance(video, str):
            return Response.error(400, "video path is required")
        mode = payload.get("mode", "auto")
        if mode not in ("fast", "auto", "precise"):
            return Response.error(400, f"invalid mode: {mode!r}")
        overrides = payload.get("overrides") or {}
        if not isinstance(overrides, dict):
            return Response.error(400, "overrides must be an object")
        try:
            start = float(payload.get("start") or 0.0)
        except (TypeError, ValueError):
            return Response.error(400, "start must be a number")
        end_raw = payload.get("end")
        try:
            end = float(end_raw) if end_raw is not None else None
        except (TypeError, ValueError):
            return Response.error(400, "end must be a number")
        try:
            job = app.start_job(video, mode=mode, overrides=overrides, start=start, end=end)
        except JobRunningError as exc:
            return Response.error(409, f"job {exc.job_id} is already running")
        except (ValueError, FileNotFoundError, OSError) as exc:
            return Response.error(400, str(exc))
        return Response.from_json({"job": job.snapshot().to_dict()}, status=202)

    @router.get("/api/status")
    def status(req: Request) -> Response:
        job = app.job
        if job is None:
            return Response.from_json({"job": None})
        return Response.from_json({"job": job.snapshot().to_dict()})

    @router.post("/api/cancel")
    def cancel(req: Request) -> Response:
        job = app.cancel_job()
        if job is None:
            return Response.error(409, "no running job")
        return Response.from_json({"cancelled": job.id})
