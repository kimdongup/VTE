import pytest

from vte.models import TextBox, TextEvent, Track, iou


def box(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


class TestIou:
    def test_identical(self):
        assert iou(box(0, 0, 10, 10), box(0, 0, 10, 10)) == 1.0

    def test_disjoint(self):
        assert iou(box(0, 0, 10, 10), box(20, 20, 30, 30)) == 0.0

    def test_half_overlap(self):
        assert iou(box(0, 0, 10, 10), box(5, 0, 15, 10)) == pytest.approx(50 / 150)

    def test_zero_area(self):
        assert iou(box(0, 0, 0, 0), box(0, 0, 10, 10)) == 0.0


class TestTextBox:
    def test_rect_center_height(self):
        b = TextBox(box(10, 20, 30, 60))
        assert b.rect == (10.0, 20.0, 30.0, 60.0)
        assert b.center == (20.0, 40.0)
        assert b.height == 40.0

    def test_moved_preserves_shape(self):
        b = TextBox(box(0, 0, 10, 10)).moved(5, -5)
        assert b.rect == (5.0, -5.0, 15.0, 5.0)


class TestTrack:
    def test_last_box_and_duration(self):
        t = Track(id=1)
        t.boxes[3] = TextBox(box(0, 0, 10, 10))
        t.boxes[7] = TextBox(box(0, 1, 10, 11))
        t.start_ts, t.end_ts = 1.0, 4.5
        assert t.last_box is not None and len(t.last_box.pts) == 4
        assert t.duration == pytest.approx(3.5)

    def test_empty_track(self):
        t = Track(id=1)
        assert t.last_box is None and t.duration == 0.0


class TestTextEvent:
    def test_defaults(self):
        e = TextEvent(start=1.0, end=2.0, text="안녕")
        assert e.confidence == 1.0 and e.boxes == []
