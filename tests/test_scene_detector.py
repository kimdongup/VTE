import numpy as np

from vte.scene_detector import SceneDetector, boxes_changed, frame_diff


def frame(color):
    img = np.full((36, 64, 3), color, dtype=np.uint8)
    return img


class TestFrameDiff:
    def test_identical_frames_zero(self):
        f = frame(128)
        assert frame_diff(f, f) == 0.0

    def test_different_frames_high(self):
        d = frame_diff(frame(0), frame(255))
        assert d > 0.9


class TestBoxesChanged:
    def test_same_layout_false(self):
        a = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
        assert boxes_changed(a, [list(p) for p in a]) is False

    def test_count_mismatch_true(self):
        a = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
        assert boxes_changed(a, []) is True

    def test_moved_box_true(self):
        a = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
        b = [[(50, 50), (60, 50), (60, 60), (50, 60)]]
        assert boxes_changed(a, b) is True


class TestSceneDetector:
    def test_first_frame_processes(self):
        sd = SceneDetector(threshold=0.12)
        assert sd.should_process(frame(10)) is True

    def test_static_frame_skipped(self):
        sd = SceneDetector(threshold=0.12)
        f = frame(100)
        sd.should_process(f)
        assert sd.should_process(f.copy()) is False

    def test_scene_change_processed(self):
        sd = SceneDetector(threshold=0.12)
        sd.should_process(frame(0))
        assert sd.should_process(frame(255)) is True

    def test_layout_change_forces_process(self):
        sd = SceneDetector(threshold=0.12)
        f = frame(100)
        sd.should_process(f, [])
        moved = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
        assert sd.should_process(f.copy(), moved) is True
