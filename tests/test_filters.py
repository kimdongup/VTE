"""filters 단위 테스트: is_logo / stable_across."""
from __future__ import annotations

import pytest

from vte.filters import is_logo, stable_across
from vte.models import TextBox, TextEvent


def make_event(
    start: float,
    end: float,
    text: str = "로고",
    pts: list[tuple[float, float]] | None = None,
) -> TextEvent:
    """테스트용 TextEvent 생성 헬퍼."""
    if pts is None:
        pts = [(0.0, 0.0), (100.0, 0.0), (100.0, 30.0), (0.0, 30.0)]
    return TextEvent(start=start, end=end, text=text, boxes=[TextBox(pts, 1.0)])


class TestIsLogo:
    def test_duration_zero_is_defended(self):
        ev = make_event(0.0, 5.0)
        assert is_logo(ev, video_duration=0.0) is False
        assert is_logo(ev, video_duration=-1.0) is False

    def test_boundary_at_ratio_times_duration(self):
        duration = 10.0
        ratio = 0.8
        threshold = duration * ratio  # 8.0s

        at = make_event(0.0, threshold)
        just_below = make_event(0.0, threshold - 0.01)
        just_above = make_event(0.0, threshold + 0.01)

        assert is_logo(at, duration, ratio=ratio) is True
        assert is_logo(just_below, duration, ratio=ratio) is False
        assert is_logo(just_above, duration, ratio=ratio) is True

    def test_short_event_is_not_logo(self):
        ev = make_event(2.0, 3.0)
        assert is_logo(ev, video_duration=60.0) is False


class TestStableAcross:
    def test_single_event_is_stable(self):
        assert stable_across([make_event(0.0, 10.0)]) is True

    def test_fixed_position_events_are_stable(self):
        events = [
            make_event(0.0, 10.0),
            make_event(11.0, 20.0),
            make_event(21.0, 30.0),
        ]
        assert stable_across(events) is True

    def test_moved_position_is_not_stable(self):
        moved_pts = [(200.0, 0.0), (300.0, 0.0), (300.0, 30.0), (200.0, 30.0)]
        events = [
            make_event(0.0, 10.0),
            make_event(11.0, 20.0, pts=moved_pts),
        ]
        assert stable_across(events) is False

    def test_large_gap_is_not_stable(self):
        events = [
            make_event(0.0, 10.0),
            make_event(20.0, 30.0),  # gap = 10 > window(기본 5.0)
        ]
        assert stable_across(events) is False

    def test_small_gap_within_window_is_stable(self):
        events = [
            make_event(0.0, 10.0),
            make_event(14.0, 20.0),  # gap = 4 < 5.0
        ]
        assert stable_across(events) is True

    def test_empty_boxes_is_not_stable(self):
        a = make_event(0.0, 10.0)
        b = TextEvent(start=11.0, end=20.0, text="x", boxes=[])
        assert stable_across([a, b]) is False

    def test_empty_list_is_stable(self):
        assert stable_across([]) is True
