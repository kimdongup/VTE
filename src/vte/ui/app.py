"""Extraction job state shared between the HTTP layer and the pipeline.

:func:`vte.pipeline.run_extract` 의 선택적 ``on_progress`` 콜백으로 진행
스냅샷을 받아 구독자(SSE 핸들러)에게 브로드캐스트한다. 한 번에 하나의 잡만
실행되며, 시작 요청은 잡 객체를 돌려주고 결과는 이벤트로 전달된다.
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config import Config, Mode
from ..models import TextEvent


@dataclass
class JobSnapshot:
    """클라이언트에 노출되는 잡 상태 (JSON 직렬화 가능)."""

    id: str
    video: str
    mode: str
    state: str  # running | done | error
    progress: dict[str, Any] | None = None
    events: list[dict[str, Any]] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "video": self.video,
            "mode": self.mode,
            "state": self.state,
            "progress": self.progress,
            "events": self.events,
            "error": self.error,
        }


def _event_dict(e: TextEvent) -> dict[str, Any]:
    return {
        "start": round(e.start, 3),
        "end": round(e.end, 3),
        "text": e.text,
        "confidence": round(e.confidence, 4),
    }


class ExtractionJob:
    """백그라운드 스레드에서 파이프라인을 실행하고 진행 이벤트를 방송한다."""

    def __init__(
        self,
        video: str,
        mode: Mode = "auto",
        cfg: Config | None = None,
        start: float = 0.0,
        end: float | None = None,
        extract_fn: Callable[..., list[TextEvent]] | None = None,
    ) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.video = video
        self.mode = mode
        self.start_ts = start
        self.end_ts = end
        self._cfg = cfg or Config.for_mode(mode)
        # 테스트 주입용: 기본은 실제 파이프라인 (lazy import로 엔진 분리 유지)
        self._extract_fn = extract_fn
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._snapshot = JobSnapshot(id=self.id, video=video, mode=mode, state="running")

    # ---- 구독 관리 -------------------------------------------------

    def subscribe(self) -> queue.Queue:
        """진행 이벤트 구독 채널을 연다. 연결 직후 스냅샷 이벤트를 먼저 넣는다."""
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            q.put(("snapshot", self._snapshot.to_dict()))
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _publish(self, kind: str, payload: Any) -> None:
        with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            q.put((kind, payload))

    # ---- 실행 제어 -------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("job already started")
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"vte-job-{self.id}")
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def snapshot(self) -> JobSnapshot:
        with self._lock:
            return self._snapshot

    # ---- 내부 -----------------------------------------------------

    def _set(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._snapshot, key, value)

    def _run(self) -> None:
        from ..pipeline import ProgressUpdate, run_extract  # lazy: 엔진 분리 유지

        def on_progress(update: ProgressUpdate) -> None:
            payload = {
                "ts": round(update.ts, 3),
                "duration": round(update.duration, 3),
                "frame_idx": update.frame_idx,
                "processed": update.processed,
                "detections": [
                    [[round(x, 1), round(y, 1)] for x, y in pts] for pts in update.detections
                ],
                "active": update.active,
                "closed": update.closed,
            }
            self._set(progress=payload)
            self._publish("progress", payload)

        extract = self._extract_fn or run_extract
        try:
            events = extract(
                self.video,
                self._cfg,
                start=self.start_ts,
                end=self.end_ts,
                on_progress=on_progress,
                should_stop=self._stop.is_set,
            )
        except Exception as exc:  # noqa: BLE001 - 잡 스레드 오류는 상태로 전달
            self._set(state="error", error=f"{type(exc).__name__}: {exc}")
            self._publish("error", self._snapshot.error)
            return
        result = [_event_dict(e) for e in events]
        self._set(state="done", events=result)
        self._publish("done", result)


class ExtractionApp:
    """HTTP 레이어가 조작하는 애플리케이션 퍼시드.

    실행 중인 잡이 있으면 새 시작을 거부한다(409). 기능이 추가될 때마다 이
    클래스를 수정하기보다, 라우트 모듈이 필요한 상태만 참조하도록 설계했다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: ExtractionJob | None = None

    @property
    def job(self) -> ExtractionJob | None:
        with self._lock:
            return self._job

    def start_job(
        self,
        video: str,
        mode: Mode = "auto",
        overrides: dict[str, Any] | None = None,
        start: float = 0.0,
        end: float | None = None,
    ) -> ExtractionJob:
        with self._lock:
            if self._job is not None and self._job.snapshot().state == "running":
                raise JobRunningError(self._job.id)
            cfg = Config.with_overrides(mode, overrides)
            job = ExtractionJob(video, mode=mode, cfg=cfg, start=start, end=end)
            self._job = job
        job.start()
        return job

    def cancel_job(self) -> ExtractionJob | None:
        job = self.job
        if job is not None and job.snapshot().state == "running":
            job.cancel()
            return job
        return None


class JobRunningError(RuntimeError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"job {job_id} is already running")
        self.job_id = job_id

