"""preprocess 단위 테스트: enhance / crop_box / sharpness."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from vte.preprocess import crop_box, enhance, sharpness


def _gradient_bgr(width=320, height=180, lo=110, hi=150) -> np.ndarray:
    """좌우 방향 완만한 그레이디언트(저대비) BGR 이미지."""
    ramp = np.tile(np.linspace(lo, hi, width, dtype=np.float32), (height, 1))
    gray = ramp.astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


class TestEnhance:
    def test_clahe_increases_contrast(self):
        img = _gradient_bgr()
        before = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std()
        out = enhance(img)
        after = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).std()
        assert after > before

    def test_low_res_input_is_upscaled(self):
        img = _gradient_bgr(width=320, height=180)  # 높이 180 < 720
        out = enhance(img)
        h, w = out.shape[:2]
        assert h > 180 or w > 320  # 업스케일 발생
        assert max(h, w) <= 2000  # 상한 내 (이 입력은 기존 코드에서도 통과)

    def test_upscale_side_cap_2000(self):
        # DEFECT-2 해결됨: enhance가 최장 변 2000px 상한을 적용한다.
        img = _gradient_bgr(width=640, height=120)
        out = enhance(img)
        h, w = out.shape[:2]
        assert max(h, w) <= 2000


class TestCropBox:
    def test_interior_crop_size(self):
        frame = np.zeros((100, 80, 3), dtype=np.uint8)
        pts = [(20.0, 10.0), (60.0, 40.0)]
        crop = crop_box(frame, pts, pad=4)
        # x: 16~64, y: 6~44
        assert crop.shape[0] == 38
        assert crop.shape[1] == 48

    def test_edge_padding_is_clamped(self):
        frame = np.zeros((80, 100, 3), dtype=np.uint8)
        pts = [(95.0, 70.0), (99.0, 79.0)]  # 프레임 우하단 가장자리
        crop = crop_box(frame, pts, pad=4)
        # x2, y2는 프레임 크기로 클램프, x1/y1은 4만큼 패딩
        assert crop.shape == (80 - 66, 100 - 91, 3)
        assert crop.size > 0


class TestSharpness:
    def test_uniform_less_than_textured(self):
        uniform = np.full((60, 200), 128, dtype=np.uint8)
        rng = np.random.default_rng(42)
        textured = (rng.integers(0, 256, size=(60, 200))).astype(np.uint8)
        assert sharpness(uniform) < sharpness(textured)

    def test_uniform_is_near_zero(self):
        uniform = np.full((40, 40), 7, dtype=np.uint8)
        assert sharpness(uniform) == pytest.approx(0.0, abs=1e-6)
