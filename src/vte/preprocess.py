from __future__ import annotations

import cv2
import numpy as np

# Hard cap on the longest side after upscaling. Without it, a tiny crop
# (e.g. 75px tall) would be doubled up to 16x and handed to the OCR engine
# as an 8000px-wide image, which is extremely slow on CPU.
_MAX_UPSCALED_SIDE = 2000
_TARGET_HEIGHT = 720


def enhance(frame: np.ndarray, upscale_small: bool = True) -> np.ndarray:
    """Auto-contrast (CLAHE on L channel), light denoise, optional upscale."""
    img = frame
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    if upscale_small:
        h, w = img.shape[:2]
        target = _TARGET_HEIGHT / h
        cap = _MAX_UPSCALED_SIDE / max(h, w)
        scale = min(target, cap)
        if scale > 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return img


def deinterlace(frame: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(frame, (3, 3), 0)


def crop_box(frame: np.ndarray, pts: list[tuple[float, float]], pad: int = 4) -> np.ndarray:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x1 = max(0, int(min(xs)) - pad)
    y1 = max(0, int(min(ys)) - pad)
    x2 = min(frame.shape[1], int(max(xs)) + pad)
    y2 = min(frame.shape[0], int(max(ys)) + pad)
    return frame[y1:y2, x1:x2]


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
