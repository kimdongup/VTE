from __future__ import annotations

import cv2

from .config import Config
from .models import TextBox


class TextDetector:
    """Thin wrapper around PaddleOCR text detection. Lazy-imported."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:  # pragma: no cover - requires engine
                raise ImportError(
                    "PaddleOCR is not installed. Run: pip install -r requirements.txt"
                ) from exc
            # paddleocr 3.x builds the full OCR pipeline even when only
            # detection is needed; pin the rec model to our configured one so
            # it does not pull the default (v6) rec model, which is not
            # loadable by some paddlepaddle builds. Do not pass ``lang``:
            # with explicit model names paddleocr 3.7 ignores it and emits a
            # UserWarning.
            self._engine = PaddleOCR(
                text_detection_model_name=self.cfg.det_model,
                text_recognition_model_name=self.cfg.rec_model,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._engine

    def detect(self, image) -> list[TextBox]:
        y_offset = 0
        x_scale = 1.0
        y_scale = 1.0
        target = image
        if self.cfg.roi_band is not None:
            r0, r1 = self.cfg.roi_band
            height = image.shape[0]
            y0 = max(0, int(round(height * r0)))
            y1 = min(height, int(round(height * r1)))
            if y1 > y0:
                y_offset = y0
                target = image[y0:y1]
        # Downscale the detection input so its LONGEST side fits the cap. Using
        # the longest side (not width) makes the cap effective on portrait /
        # vertical video too: a 826x1460 frame with a width cap of 960 would
        # skip downscaling entirely (826 < 960) and run detection at full 1460
        # height. The band crop happens first (in original coordinates); after
        # downscaling, points are restored with a per-axis factor so band offset
        # stays exact.
        max_side = self.cfg.det_max_side
        h, w = target.shape[:2]
        longest = max(h, w)
        if max_side is not None and longest > max_side:
            scale = max_side / longest
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            target = cv2.resize(
                target, (new_w, new_h), interpolation=cv2.INTER_AREA
            )
            x_scale = w / new_w
            y_scale = h / new_h
        result = self._get_engine().predict(target)
        boxes: list[TextBox] = []
        for page in result:
            data = getattr(page, "res", page) or {}
            polys = data.get("dt_polys") or []
            scores = data.get("dt_scores") or []
            for i, poly in enumerate(polys):
                pts = [
                    (
                        float(p[0]) * x_scale,
                        float(p[1]) * y_scale + y_offset,
                    )
                    for p in poly
                ]
                score = float(scores[i]) if i < len(scores) else 1.0
                box = TextBox(pts, score)
                if self.cfg.min_box_height <= box.height <= self.cfg.max_box_height:
                    boxes.append(box)
        return boxes
