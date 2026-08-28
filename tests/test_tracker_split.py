"""RegionTracker.split / extend_static / finish_all 경계 동작 단위 테스트.

split은 DEFECT-1 근본 해결로 추가된 API다: 내용이 바뀐 안정 박스에 대해
기존 트랙을 종료 목록으로 옮기고 새 id의 후계 트랙을 같은 박스로 시작한다.
extend_static은 장면 스킵 샘플에서 healthy 트랙의 end_ts를 연장한다.
"""
from __future__ import annotations

import pytest

from vte.config import Config
from vte.models import TextBox
from vte.tracker import RegionTracker


def box(x, y, w=100, h=30):
    return TextBox([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


class TestSplit:
    def test_split_finishes_old_track_and_spawns_successor(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])
        old_id = tr.tracks[0].id

        succ = tr.split(old_id, 5, 1.65, box(100, 500))

        assert succ is not None
        assert succ.id != old_id
        assert succ.start_ts == pytest.approx(1.65)
        assert succ.end_ts == pytest.approx(1.65)
        # 활성 목록에는 후계 트랙만 남는다
        assert [t.id for t in tr.tracks] == [succ.id]
        # 기존 트랙은 종료 목록으로 이동해 텍스트 이력을 보존한다
        done = tr.finish_all()
        assert {t.id for t in done} == {old_id, succ.id}

    def test_split_preserves_old_history_and_successor_is_fresh(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])
        tr.update(1, 0.33, [box(100, 500)])
        old_id = tr.tracks[0].id

        succ = tr.split(old_id, 2, 0.66, box(100, 500))
        done = {t.id: t for t in tr.finish_all()}

        assert len(done[old_id].boxes) == 2
        assert done[old_id].end_ts == pytest.approx(0.33)
        assert list(succ.boxes.keys()) == [2]
        assert done[succ.id].start_ts == pytest.approx(0.66)

    def test_split_unknown_id_returns_none_without_side_effects(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])
        before = list(tr.tracks)
        next_id_before = tr.tracks[0].id

        result = tr.split(999, 1, 0.33, box(100, 500))

        assert result is None
        assert len(tr.tracks) == 1
        assert tr.tracks[0] is before[0]
        assert tr.tracks[0].id == next_id_before


class TestExtendStatic:
    def test_extends_healthy_track_end_ts(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])

        tr.extend_static(0.66)

        assert tr.tracks[0].end_ts == pytest.approx(0.66)
        assert tr.tracks[0].start_ts == pytest.approx(0.0)

    def test_does_not_extend_missed_track(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])
        tr.update(1, 0.33, [])  # 매칭 실패 -> missed 상태

        tr.extend_static(0.66)

        # missed 트랙은 스킵 구간으로 연장되지 않는다(end_ts 불변).
        assert tr.tracks[0].end_ts == pytest.approx(0.0)

    def test_empty_tracker_is_safe(self):
        tr = RegionTracker()
        tr.extend_static(1.0)  # 예외 없어야 함
        assert tr.tracks == []


class TestAfterFinishAll:
    def test_split_after_finish_all_returns_none(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])
        tr.finish_all()

        result = tr.split(1, 1, 0.33, box(100, 500))

        assert result is None
        assert tr.tracks == []

    def test_extend_static_after_finish_all_is_safe(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])
        tr.finish_all()

        tr.extend_static(5.0)  # 예외 없어야 함

        assert tr.tracks == []

    def test_finish_all_twice_returns_empty_second_time(self):
        tr = RegionTracker()
        tr.update(0, 0.0, [box(100, 500)])

        first = tr.finish_all()
        second = tr.finish_all()

        assert len(first) == 1
        assert second == []


class TestSplitThenContinueTracking:
    def test_successor_matches_following_boxes(self):
        """split 후 후계 트랙이 이후 프레임 박스를 정상 흡수하는지."""
        cfg = Config()
        tr = RegionTracker(cfg)
        tr.update(0, 0.0, [box(100, 500)])
        old_id = tr.tracks[0].id
        succ = tr.split(old_id, 1, 0.33, box(100, 500))

        visible = tr.update(2, 0.66, [box(101, 501)])

        assert [t.id for t in visible] == [succ.id]
        assert visible[0].boxes and max(visible[0].boxes) == 2
