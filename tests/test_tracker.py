import pytest

from vte.config import Config
from vte.models import TextBox
from vte.tracker import RegionTracker


def box(x, y, w=100, h=30):
    return TextBox([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


class TestRegionTracker:
    def test_stationary_box_single_track(self):
        tr = RegionTracker(Config(max_missed=1))
        tr.update(0, 0.0, [box(100, 500)])
        tr.update(1, 0.33, [box(101, 501)])
        tr.update(2, 0.66, [box(100, 500)])
        done = tr.finish_all()
        assert len(done) == 1
        assert done[0].start_ts == 0.0
        assert done[0].end_ts == pytest.approx(0.66)

    def test_moving_box_stays_one_track(self):
        tr = RegionTracker()
        for i in range(6):
            tr.update(i, i * 0.33, [box(50 + i * 20, 500)])
        done = tr.finish_all()
        assert len(done) == 1 and len(done[0].boxes) == 6

    def test_gap_beyond_max_missed_splits(self):
        tr = RegionTracker(Config(max_missed=2))
        tr.update(0, 0.0, [box(100, 500)])
        tr.update(1, 0.33, [])
        tr.update(2, 0.66, [])
        tr.update(3, 0.99, [])
        tr.update(4, 1.32, [box(100, 500)])
        done = tr.finish_all()
        assert len(done) == 2

    def test_two_regions_tracked_independently(self):
        tr = RegionTracker()
        for i in range(3):
            tr.update(i, i * 0.33, [box(50, 100), box(600, 80)])
        done = tr.finish_all()
        assert len(done) == 2

    def test_new_object_gets_new_id(self):
        tr = RegionTracker()
        a = tr.update(0, 0.0, [box(0, 0)])
        b = tr.update(1, 0.33, [box(800, 800)])
        ids_a = {t.id for t in a}
        ids_b = {t.id for t in b if t.id not in ids_a}
        assert len(ids_b) == 1

    def test_iou_boundary_050(self):
        tr = RegionTracker(Config(iou_threshold=0.5))
        tr.update(0, 0.0, [box(0, 0)])
        # shifted by exactly half width -> IoU ~0.333, below threshold
        res = tr.update(1, 0.33, [box(60, 0)])
        assert any(t.last_box.rect[0] == 60 for t in res)
