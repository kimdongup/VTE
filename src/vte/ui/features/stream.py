"""진행 상황 SSE 스트리밍 라우트.

GET /api/events — 실행 중인 잡의 진행/완료/오류 이벤트를 SSE로 흘려보낸다.

연결을 끊지 않는 것이 중요하다: EventSource는 서버가 스트림을 닫으면 자동
재연결하는데, 잡이 없을 때 바로 닫으면 무한 재연결 루프가 된다. 따라서 잡이
없는 동안엔 ping을 보내며 기다리고, 잡이 생기면 그 잡에 구독한다.
"""

from __future__ import annotations

import queue
import time
from typing import TYPE_CHECKING

from ..server import Request, SSEStream

if TYPE_CHECKING:
    from ..app import ExtractionApp
    from ..server import Router

_WAIT_JOB_POLL = 0.5  # 잡 등장 대기 주기(초)
_PING_EVERY = 15.0   # 연결 유지 ping 주기(초)


def register(router: "Router", app: "ExtractionApp") -> None:
    @router.get("/api/events")
    def events(req: Request) -> SSEStream:
        def generator():
            # 1) 잡이 나타날 때까지 대기 (ping으로 연결 유지)
            job = app.job
            while job is None:
                yield "ping", {"waiting": True}
                time.sleep(_WAIT_JOB_POLL)
                job = app.job

            # 2) 잡에 구독하고 이벤트를 중계
            q = job.subscribe()
            last_ping = time.monotonic()
            try:
                # 구독 전에 이미 끝난 잡이면 남은 이벤트가 없으므로 즉시 통지.
                snap_state = job.snapshot().state
                if snap_state == "done":
                    yield "done", {"events": job.snapshot().events}
                    return
                if snap_state == "error":
                    yield "error", {"message": job.snapshot().error}
                    return
                while True:
                    try:
                        kind, payload = q.get(timeout=1.0)
                    except queue.Empty:
                        if time.monotonic() - last_ping >= _PING_EVERY:
                            yield "ping", {"id": job.id}
                            last_ping = time.monotonic()
                        continue
                    last_ping = time.monotonic()
                    if kind == "snapshot":
                        yield "snapshot", {"job": payload}
                    elif kind == "progress":
                        yield "progress", payload
                    elif kind == "done":
                        yield "done", {"events": payload}
                        return
                    elif kind == "error":
                        yield "error", {"message": payload}
                        return
            finally:
                job.unsubscribe(q)

        return SSEStream(events=generator)

