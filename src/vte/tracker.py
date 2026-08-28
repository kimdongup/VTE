from __future__ import annotations

from collections.abc import Callable

from .config import Config
from .models import TextBox, Track, iou


def _center_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class RegionTracker:
    """Greedy IoU matching with center-distance fallback and EMA smoothing.

    Swappable via the ``match`` method protocol (SORT upgrade path).
    """

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.tracks: list[Track] = []
        self._finished: list[Track] = []
        self._next_id = 1
        self._missed: dict[int, int] = {}

    def update(self, frame_idx: int, ts: float, boxes: list[TextBox]) -> list[Track]:
        unmatched = list(range(len(self.tracks)))
        for box in boxes:
            best = self._best_iou_match(box, unmatched)
            if best < 0:
                best = self._nearest_center_match(box, unmatched)
            if best >= 0:
                self._attach(best, frame_idx, ts, box)
                unmatched.remove(best)
            else:
                self._spawn(frame_idx, ts, box)
        self._age_unmatched(unmatched)
        return [t for t in self.tracks if t.id not in self._missed]

    def _best_iou_match(self, box: TextBox, candidates: list[int]) -> int:
        best, best_score = -1, self.cfg.iou_threshold
        for ti in candidates:
            last = self.tracks[ti].last_box
            if last is None:
                continue
            score = iou(last.pts, box.pts)
            if score > best_score:
                best, best_score = ti, score
        return best

    def _nearest_center_match(self, box: TextBox, candidates: list[int]) -> int:
        for ti in candidates:
            last = self.tracks[ti].last_box
            if last is None:
                continue
            limit = max(last.height, box.height) * (1 + self.cfg.center_dist_ratio)
            if _center_dist(last.center, box.center) <= limit:
                return ti
        return -1

    def _spawn(self, frame_idx: int, ts: float, box: TextBox) -> Track:
        track = Track.starting(id=self._next_id, frame_idx=frame_idx, ts=ts, box=box)
        self._next_id += 1
        self.tracks.append(track)
        return track

    def _attach(self, ti: int, frame_idx: int, ts: float, box: TextBox) -> None:
        track = self.tracks[ti]
        track.boxes[frame_idx] = self._smoothed(track.last_box, box)
        track.end_ts = ts
        self._missed.pop(track.id, None)

    def _smoothed(self, last: TextBox | None, box: TextBox) -> TextBox:
        if last is None or last.pts == box.pts:
            return box
        a = self.cfg.ema_alpha
        smoothed_pts = [
            (a * p + (1 - a) * q, a * r + (1 - a) * s)
            for (p, r), (q, s) in zip(box.pts, last.pts)
        ]
        return TextBox(smoothed_pts, box.score)

    def _age_unmatched(self, unmatched: list[int]) -> None:
        """Bump miss counters for unmatched tracks and retire the expired ones."""
        expired = set()
        for ti in unmatched:
            tid = self.tracks[ti].id
            self._missed[tid] = self._missed.get(tid, 0) + 1
            if self._missed[tid] > self.cfg.max_missed:
                expired.add(tid)
        if expired:
            self.tracks, retired = _partition(self.tracks, lambda t: t.id not in expired)
            self._finished.extend(retired)

    def close_track(self, track_or_id: Track | int, end_ts: float | None = None) -> Track | None:
        """Finish an active track now and move it to the finished list.

        Accepts either the track object or its id. ``end_ts``, when given,
        is the last timestamp the region was known to be on screen (callers
        may clamp it, e.g. to just before a text swap). This is the only
        sanctioned way to retire a single active track early; external code
        must not mutate ``Track.end_ts`` directly. Returns the finished
        track, or ``None`` if no active track matches.
        """
        tid = track_or_id.id if isinstance(track_or_id, Track) else track_or_id
        for i, track in enumerate(self.tracks):
            if track.id != tid:
                continue
            if end_ts is not None:
                track.end_ts = end_ts
            del self.tracks[i]
            self._finished.append(track)
            self._missed.pop(tid, None)
            return track
        return None

    def split(
        self,
        track_id: int,
        frame_idx: int,
        ts: float,
        box: TextBox,
        *,
        end_ts: float | None = None,
    ) -> Track | None:
        """Force-finish a track and spawn a same-box successor.

        Used when the pixels inside a stable box change to unrelated text:
        the old track is moved to the finished list (keeping its texts) and a
        new track with a fresh id takes over from ``ts``. When ``end_ts`` is
        given, the finished track's end is clamped to it first (typically one
        sample before ``ts``, since both texts briefly shared the box).
        The successor occupies the predecessor's slot so track ordering in
        ``self.tracks`` stays stable.
        """
        idx = next((i for i, t in enumerate(self.tracks) if t.id == track_id), -1)
        if idx < 0:
            return None
        self.close_track(track_id, end_ts)
        successor = self._spawn(frame_idx, ts, box)
        self.tracks.insert(idx, self.tracks.pop())
        return successor

    def extend_static(self, ts: float) -> None:
        """Push ``end_ts`` of healthy tracks across scene-skipped samples.

        A skipped sample is nearly identical to the last processed one, so any
        track that is not currently missing still covers that timestamp.
        Tracks in missed state are not extended: their region may have
        disappeared.
        """
        for track in self.tracks:
            if track.id not in self._missed:
                track.end_ts = ts

    def finish_all(self) -> list[Track]:
        self._finished.extend(self.tracks)
        self.tracks.clear()
        done, self._finished = self._finished, []
        return done


def _partition(items: list[Track], keep: Callable[[Track], bool]) -> tuple[list[Track], list[Track]]:
    kept, dropped = [], []
    for item in items:
        (kept if keep(item) else dropped).append(item)
    return kept, dropped
