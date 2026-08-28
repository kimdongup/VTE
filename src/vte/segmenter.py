from __future__ import annotations

from rapidfuzz import fuzz

from .config import Config
from .filters import is_logo
from .models import TextEvent, Track
from .postprocess import normalize

_VOTE_MATCH_RATIO = 80.0


def best_text(track: Track, vote: int = 3) -> tuple[str, float]:
    """Pick the most-voted normalized text; require a majority when voting."""
    raw_scores = track.scores if len(track.scores) == len(track.texts) else [1.0] * len(track.texts)
    valid = [(normalize(t), s) for t, s in zip(track.texts, raw_scores) if normalize(t)]
    if not valid:
        return "", 0.0
    texts = [v[0] for v in valid]
    scores = [v[1] for v in valid]
    if len(texts) == 1:
        return texts[0], float(scores[0])
    counts: dict[str, list[float]] = {}
    for t, s in zip(texts[:vote], scores[:vote]):
        matched = False
        for key in list(counts):
            if fuzz.ratio(key, t) >= _VOTE_MATCH_RATIO:
                counts[key].append(s)
                matched = True
                break
        if not matched:
            counts[t] = [s]
    winner = max(counts, key=lambda k: len(counts[k]))
    if len(counts[winner]) < 2:
        return "", 0.0
    vote_conf = len(counts[winner]) / min(len(texts), vote)
    avg_score = sum(counts[winner]) / len(counts[winner])
    return winner, vote_conf * avg_score


def build_events(tracks: list[Track], cfg: Config | None = None) -> list[TextEvent]:
    cfg = cfg or Config()
    ordered = sorted(tracks, key=lambda t: (t.start_ts, t.id))
    events = [e for e in (_track_to_event(t, cfg.vote_frames) for t in ordered) if e]
    events = _merge_similar(events, cfg.sim_threshold, cfg.debounce_gap)
    events = _fill_gaps(events, cfg.debounce_gap, cfg.sim_threshold)
    events = [e for e in events if e.end - e.start >= cfg.min_duration]
    return events


def _track_to_event(track: Track, vote_frames: int) -> TextEvent | None:
    """Convert one track to a TextEvent, or None when voting is inconclusive."""
    text, conf = best_text(track, vote_frames)
    if not text or conf < 1 / max(vote_frames, 2):
        return None
    boxes = [track.boxes[k] for k in sorted(track.boxes)]
    return TextEvent(
        start=track.start_ts,
        end=track.end_ts,
        text=text,
        boxes=[boxes[0]],
        confidence=conf,
    )


def drop_logos(events: list[TextEvent], video_duration: float, cfg: Config | None = None):
    cfg = cfg or Config()
    kept, logos = [], []
    for e in events:
        if is_logo(e, video_duration, cfg.logo_ratio):
            logos.append(e)
        else:
            kept.append(e)
    return kept, logos


def _merge_similar(
    events: list[TextEvent], threshold: float, max_gap: float
) -> list[TextEvent]:
    merged: list[TextEvent] = []
    for e in events:
        if (
            merged
            and fuzz.ratio(merged[-1].text, e.text) >= threshold
            and e.start - merged[-1].end <= max_gap
        ):
            prev = merged[-1]
            prev.end = e.end
            prev.confidence = max(prev.confidence, e.confidence)
        else:
            merged.append(e)
    return merged


def _fill_gaps(events: list[TextEvent], max_gap: float, threshold: float) -> list[TextEvent]:
    if not events:
        return events
    out = [events[0]]
    for e in events[1:]:
        prev = out[-1]
        if e.start - prev.end <= max_gap and fuzz.ratio(prev.text, e.text) >= threshold:
            prev.end = e.end
        else:
            out.append(e)
    return out
