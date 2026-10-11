from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import cv2
import numpy as np
from rapidfuzz import fuzz

from .config import Config
from .detector import TextDetector
from .models import TextBox, TextEvent, Track
from .postprocess import is_mostly_korean, normalize
from .preprocess import crop_box, enhance
from .recognizer import Recognizer
from .scene_detector import SceneDetector
from .segmenter import best_text, build_events, drop_logos
from .tracker import RegionTracker
from .video_reader import VideoReader


@dataclass
class ProgressUpdate:
    """파이프라인 샘플 하나의 진행 스냅샷 (UI 진행 표시용).

    ``closed`` 는 완료된 트랙 기준 확정 구간 전체 리스트이며, 매 스냅샷마다
    tracker.finished 전체에서 다시 계산되므로 누적·병합 로직이 필요 없다.
    """

    ts: float
    duration: float
    frame_idx: int
    processed: bool  # False = 장면전환으로 건너뛴 정적 샘플
    detections: list[list[tuple[float, float]]]
    active: list[dict]
    closed: list[dict]

# A crop is re-recognized only when its content changed since the last
# recognition. Change is measured as mean absolute difference between small
# grayscale thumbnails; below this threshold the crop is treated as identical
# (static subtitle) and OCR is skipped. Same-position subtitle text swaps
# produce a small but clear signal (~0.008 on synth fixtures) while decoded
# static content sits at ~0, so keep the threshold well below the signal.
_CROP_CHANGE_THRESHOLD = 0.003
_THUMB_SIZE = (128, 32)
_MIN_CROP_SIDE = 4


class _RecState:
    """Per-track incremental recognition state."""

    __slots__ = ("sig", "confirmed", "score")

    def __init__(self) -> None:
        self.sig: np.ndarray | None = None
        self.confirmed: str = ""
        self.score: float = 0.0

    @classmethod
    def with_reading(cls, sig: np.ndarray, confirmed: str, score: float) -> "_RecState":
        """State already holding a confirmed reading (split hand-over)."""
        state = cls()
        state.update(sig, confirmed, score)
        return state

    def update(self, sig: np.ndarray, confirmed: str, score: float) -> None:
        self.sig = sig
        self.confirmed = confirmed
        self.score = score


class RecognitionCoordinator:
    """Keeps active tracks' recognized text in sync with their crops.

    Division of labour with the :class:`RegionTracker`: the tracker owns
    track lifecycle (spawning, timestamp extension, early close via
    ``close_track``/``split``); the coordinator owns only the *content* —
    appending readings to ``track.texts`` and mirroring per-track state in
    ``self._states`` keyed by track id.

    For every processed sample it re-recognizes each visible track whose
    crop content changed since the last recognition (measured on small
    grayscale thumbnails), and hands same-position text swaps over to a
    fresh track so both texts survive.
    """

    def __init__(
        self,
        cfg: Config,
        recognizer: Recognizer,
        tracker: RegionTracker,
    ) -> None:
        self._cfg = cfg
        self._recognizer = recognizer
        self._tracker = tracker
        self._sample_interval = 1.0 / cfg.sample_fps
        self._states: dict[int, _RecState] = {}

    def process_frame(
        self,
        frame_idx: int,
        ts: float,
        image: np.ndarray,
        tracks: Iterable[Track],
    ) -> None:
        """Recognize changed crops of all tracks visible at ``frame_idx``."""
        # Snapshot: split() may append a successor mid-loop; it must not be
        # revisited on the sample that spawned it.
        for track in list(tracks):
            box = track.boxes.get(frame_idx)
            if box is None:
                continue  # not seen on this sample; nothing to re-recognize
            self._process_track(track, frame_idx, ts, image, box)

    def _process_track(
        self,
        track: Track,
        frame_idx: int,
        ts: float,
        image: np.ndarray,
        box: TextBox,
    ) -> None:
        crop = crop_box(image, box.pts)
        if crop.shape[0] < _MIN_CROP_SIDE or crop.shape[1] < _MIN_CROP_SIDE:
            return
        state = self._states.get(track.id)
        if state is None:
            state = _RecState()
            self._states[track.id] = state
        thumb = _thumb(crop)
        change_threshold = getattr(self._cfg, "crop_change_threshold", _CROP_CHANGE_THRESHOLD)
        if state.sig is not None and _diff(state.sig, thumb) < change_threshold:
            return
        enhanced = enhance(crop, self._cfg.upscale_small)
        raw, score = self._recognizer.recognize(enhanced)
        text = normalize(raw)
        if not (text and is_mostly_korean(text)):
            # Keep the old signature so the content is retried on a later
            # processed sample instead of being locked out by one bad read.
            return
        if state.confirmed and fuzz.ratio(state.confirmed, text) < self._cfg.sim_threshold:
            self._hand_over(track, frame_idx, ts, box, thumb, text, score)
            return
        track.texts.append(text)
        track.scores.append(score)
        state.update(thumb, text, score)

    def _hand_over(
        self,
        track: Track,
        frame_idx: int,
        ts: float,
        box: TextBox,
        thumb: np.ndarray,
        text: str,
        score: float,
    ) -> None:
        """Same box, different subtitle: finish the current track and hand
        over to a fresh one so both texts survive.

        Data flow across the tracker boundary:

        1. ``tracker.split(...)`` retires ``track`` — its end is clamped to
           one sample before ``ts`` (both texts briefly shared this box, so
           neither may claim the swap instant) — and returns a fresh
           successor covering the same box from ``ts``.
        2. The recognized text/score move onto the successor.
        3. Recognition state follows: the old id's state is dropped and a
           fresh one, seeded with the new reading, is filed under the
           successor id so the next sample compares against it.
        """
        boundary = max(track.start_ts, ts - self._sample_interval)
        successor = self._tracker.split(
            track.id, frame_idx, ts, box, end_ts=boundary,
        )
        self._states.pop(track.id, None)
        if successor is None:
            return
        successor.texts.append(text)
        successor.scores.append(score)
        self._states[successor.id] = _RecState.with_reading(thumb, text, score)


def run_extract(
    video_path: str,
    cfg: Config | None = None,
    start: float = 0.0,
    end: float | None = None,
    on_progress: Callable[[ProgressUpdate], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[TextEvent]:
    """End-to-end pipeline: frames -> boxes -> tracks -> events.

    ``on_progress`` (선택): 샘플 처리마다 :class:`ProgressUpdate`를 전달한다.
    UI 진행 표시용이며 콜백이 없으면 기존과 동일하게 동작한다.

    ``should_stop`` (선택): 샘플 루프 진입 전에 True를 반환하면 현재까지의
    트랙(활성 포함)으로 이벤트를 만들어 조기 종료한다.
    """
    cfg = cfg or Config()
    reader = VideoReader(video_path, cfg.sample_fps)
    detector = TextDetector(cfg)
    recognizer = Recognizer(cfg)
    tracker = RegionTracker(cfg)
    scene = SceneDetector(cfg.scene_threshold)
    coordinator = RecognitionCoordinator(cfg, recognizer, tracker)

    frame_idx = 0
    prev_layout: list[list[tuple[float, float]]] = []

    def emit(ts: float, processed: bool, boxes: list[TextBox]) -> None:
        if on_progress is None:
            return
        active = []
        for t in tracker.tracks:
            if not t.texts:
                continue
            box = t.last_box
            active.append({
                "id": t.id,
                "text": t.texts[-1],
                "start": t.start_ts,
                "end": t.end_ts,
                "rect": list(box.rect) if box else None,
            })
        closed = []
        for t in tracker.finished:
            text, conf = best_text(t, cfg.vote_frames)
            if text:
                closed.append({"id": t.id, "start": t.start_ts, "end": t.end_ts, "text": text, "confidence": conf})
        on_progress(ProgressUpdate(
            ts=ts,
            duration=reader.duration,
            frame_idx=frame_idx,
            processed=processed,
            detections=[b.pts for b in boxes],
            active=active,
            closed=closed,
        ))

    for sample in reader:
        ts = sample.timestamp
        if ts < start or (end is not None and ts > end):
            continue
        if should_stop is not None and should_stop():
            break
        if not scene.should_process(sample.image, prev_layout):
            # Static frame: every healthy track still covers this timestamp.
            tracker.extend_static(ts)
            emit(ts, False, [])
            frame_idx += 1
            continue
        boxes = detector.detect(sample.image)
        prev_layout = [b.pts for b in boxes]
        tracker.update(frame_idx, ts, boxes)
        coordinator.process_frame(frame_idx, ts, sample.image, tracker.tracks)
        emit(ts, True, boxes)
        frame_idx += 1
    reader.close()

    finished: list[Track] = tracker.finish_all()
    duration = reader.duration
    events = build_events([t for t in finished if t.texts], cfg)
    events, _logos = drop_logos(events, duration, cfg)
    return events


def _thumb(crop: np.ndarray) -> np.ndarray:
    """Small grayscale thumbnail used as a change signature for a crop."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, _THUMB_SIZE)


def _diff(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute difference of two thumbnails, normalized to [0, 1]."""
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16)))) / 255.0
