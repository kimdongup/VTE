from __future__ import annotations

import cv2
import numpy as np

from .config import Config

# paddlex resizes inputs whose longest side exceeds its max_side_limit; doing
# so on a very large image (e.g. an over-upscaled crop) is extremely slow on
# CPU, so downscale defensively before handing the image to the engine.
_MAX_SIDE = 2000

# The rec model scrambles word order on tall inputs (measured on
# korean_PP-OCRv5_mobile_rec: a 40px-tall line reads correctly up to ~256px,
# wrong from ~288px), so cap the input height before prediction.
_MAX_REC_HEIGHT = 256

# The rec model assumes single-line input; feeding a multi-line band scrambles
# the reading order. Split the crop into text lines first.
_MIN_LINE_HEIGHT = 12  # px; shorter runs are noise, not lines
_LINE_GAP_TOLERANCE = 6  # px; merge runs separated by less (intra-line dips)
_PEAK_FRACTION = 0.1  # row ink threshold relative to the busiest row
_LINE_TARGET_HEIGHT = 48  # px; normalize each split line before rec

# Below this height, UI-size text loses strokes during rec (measured on real
# 1080p video: crops <~40px tall misread as '그글에 클로드를 검색ㅎ D'). Upscale
# to a readable height before the pipeline. enhance()'s upscale cannot be
# relied on for this because its _MAX_UPSCALED_SIDE cap limits wide crops
# (common for text bands) to a small factor, so short crops still arrive here.
_MIN_REC_HEIGHT = 48  # px


class Recognizer:
    """Thin wrapper around PaddleOCR recognition. Lazy-imported."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self._engine = None

    @property
    def _max_side(self) -> int:
        return getattr(self.cfg, "max_side", _MAX_SIDE)

    @property
    def _max_rec_height(self) -> int:
        return getattr(self.cfg, "max_rec_height", _MAX_REC_HEIGHT)

    @property
    def _min_rec_height(self) -> int:
        return getattr(self.cfg, "min_rec_height", _MIN_REC_HEIGHT)

    @property
    def _line_target_height(self) -> int:
        return getattr(self.cfg, "line_target_height", _LINE_TARGET_HEIGHT)

    def _get_engine(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:  # pragma: no cover - requires engine
                raise ImportError(
                    "PaddleOCR is not installed. Run: pip install -r requirements.txt"
                ) from exc
            # Pin the det model too: leaving it unset makes paddleocr 3.x
            # pull its default (v6) det model, which some paddlepaddle
            # builds cannot load. Do not pass ``lang``: with explicit model
            # names paddleocr 3.7 ignores it and emits a UserWarning.
            self._engine = PaddleOCR(
                text_detection_model_name=self.cfg.det_model,
                text_recognition_model_name=self.cfg.rec_model,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
            )
        return self._engine

    def recognize(self, image) -> tuple[str, float]:
        if isinstance(image, np.ndarray):
            image = self._ensure_min_height(image)
            image = self._clamp_size(image)
            segments = self._find_line_segments(image)
            if len(segments) > 1:
                texts: list[str] = []
                scores: list[float] = []
                for y1, y2 in segments:
                    t, s = self._predict(
                        self._normalize_line(image[y1 : y2 + 1])
                    )
                    if t:
                        texts.append(t)
                        scores.append(s)
                text = " ".join(texts).strip()
                score = max(scores) if scores else 0.0
                return text, score
        return self._predict(image)

    def _ensure_min_height(self, image) -> np.ndarray:
        h, w = image.shape[:2]
        min_h = self._min_rec_height
        if h >= min_h or h < 2:
            return image
        scale = min_h / h
        return cv2.resize(
            image,
            (max(1, int(round(w * scale))), min_h),
            interpolation=cv2.INTER_CUBIC,
        )

    def _clamp_size(self, image) -> np.ndarray:
        h, w = image.shape[:2]
        max_s = self._max_side
        max_h = self._max_rec_height
        min_h = self._min_rec_height
        if max(h, w) <= max_s and h <= max_h:
            return image
        w_scale = max_s / w if w > max_s else 1.0
        h_scale = max_h / h if h > max_h else 1.0
        scale = min(w_scale, h_scale)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        if h >= min_h and new_h < min_h:
            new_h = min_h
        return cv2.resize(
            image, (new_w, new_h), interpolation=cv2.INTER_AREA
        )

    def _normalize_line(self, line: np.ndarray) -> np.ndarray:
        h, w = line.shape[:2]
        if h < 2 or w < 2:
            return line
        target_h = self._line_target_height
        max_s = self._max_side
        scale = target_h / h
        new_h = target_h
        new_w = max(1, int(round(w * scale)))
        if new_w > max_s:
            new_w = max_s
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        return cv2.resize(
            line, (new_w, new_h), interpolation=interp
        )

    def _predict(self, image) -> tuple[str, float]:
        result = self._get_engine().predict(image)
        texts: list[str] = []
        scores: list[float] = []
        for page in result:
            data = getattr(page, "res", page) or {}
            texts.extend(data.get("rec_texts") or [])
            scores.extend(data.get("rec_scores") or [])
        text = " ".join(t for t in texts if t).strip()
        score = max(scores) if scores else (1.0 if text else 0.0)
        return text, score

    def _find_line_segments(self, image) -> list[tuple[int, int]]:
        """Return (y1, y2) row ranges of text lines, top to bottom.

        Empty list means "single line / not splittable" and the caller
        falls back to one recognition call on the whole crop.
        """
        h = image.shape[0]
        # Two valid lines cannot fit below the minimum height.
        if h < _MIN_LINE_HEIGHT * 2:
            return []
        profile = self._row_ink_profile(image)
        peak = int(profile.max()) if profile.size else 0
        if peak <= 0:
            return []
        mask = profile >= max(1, int(peak * _PEAK_FRACTION))
        rows = np.flatnonzero(mask)
        if rows.size == 0:
            return []
        segments: list[tuple[int, int]] = []
        start = prev = int(rows[0])
        for r in rows[1:]:
            r = int(r)
            if r - prev > _LINE_GAP_TOLERANCE:
                segments.append((start, prev))
                start = r
            prev = r
        segments.append((start, prev))
        segments = [
            (y1, y2) for y1, y2 in segments if y2 - y1 + 1 >= _MIN_LINE_HEIGHT
        ]
        return segments if len(segments) > 1 else []

    @staticmethod
    def _row_ink_profile(image) -> np.ndarray:
        gray = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if image.ndim == 3
            else image
        )
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Text pixels are the minority class; keep that polarity.
        if np.count_nonzero(bw) > bw.size // 2:
            bw = cv2.bitwise_not(bw)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        return bw.sum(axis=1, dtype=np.int64)
