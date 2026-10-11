from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["fast", "auto", "precise"]


@dataclass(frozen=True)
class Config:
    sample_fps: float = 3.0
    scene_threshold: float = 0.12
    iou_threshold: float = 0.5
    center_dist_ratio: float = 0.5
    max_missed: int = 2
    ema_alpha: float = 0.6
    sim_threshold: float = 85.0
    debounce_gap: float = 0.5
    min_duration: float = 0.5
    conf_threshold: float = 0.9
    logo_ratio: float = 0.8
    vote_frames: int = 3
    rec_model: str = "korean_PP-OCRv5_mobile_rec"
    det_model: str = "PP-OCRv5_server_det"
    roi_band: tuple[float, float] | None = None
    # Downscale the detection input so its LONGEST side does not exceed this.
    # Longest-side (not width) so the cap actually binds on portrait/vertical
    # video, where width < height and a width-only cap would be a no-op.
    det_max_side: int | None = 1280
    upscale_small: bool = True
    min_box_height: int = 8
    max_box_height: int = 200
    line_target_height: int = 48
    max_side: int = 2000
    min_rec_height: int = 48
    max_rec_height: int = 256
    crop_change_threshold: float = 0.003
    lang: str = "korean"

    @classmethod
    def for_mode(cls, mode: Mode) -> "Config":
        if mode == "fast":
            return cls(
                sample_fps=2.0,
                det_model="PP-OCRv5_mobile_det",
                det_max_side=960,
            )
        if mode == "precise":
            return cls(
                sample_fps=6.0,
                conf_threshold=0.8,
                vote_frames=5,
                debounce_gap=0.4,
                scene_threshold=0.06,
                # server det at original 1080p does not complete (>30min per
                # frame, measured); 1280 keeps server-det quality feasible.
                det_max_side=1280,
            )
        return cls()
