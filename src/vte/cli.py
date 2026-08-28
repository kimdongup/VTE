from __future__ import annotations

import argparse
import sys
from pathlib import Path

import dataclasses

from .config import Config
from .exporter import FORMATS, export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vte", description="Extract on-screen Korean text and time intervals from video."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("video")
        p.add_argument("--mode", choices=["fast", "auto", "precise"], default="auto")
        p.add_argument("--start", type=float, default=0.0)
        p.add_argument("--end", type=float, default=None)
        p.add_argument("--format", default="json", choices=sorted(FORMATS))
        p.add_argument("--output", default=None)

        # Advanced pipeline parameters
        p.add_argument("--sample-fps", type=float, default=None, help="Frame sampling rate")
        p.add_argument("--scene-threshold", type=float, default=None, help="Scene change threshold")
        p.add_argument("--iou-threshold", type=float, default=None, help="Tracking IoU threshold")
        p.add_argument("--sim-threshold", type=float, default=None, help="Text similarity threshold")
        p.add_argument("--debounce-gap", type=float, default=None, help="Debounce gap in seconds")
        p.add_argument("--min-duration", type=float, default=None, help="Minimum event duration in seconds")
        p.add_argument("--conf-threshold", type=float, default=None, help="Confidence threshold")
        p.add_argument("--logo-ratio", type=float, default=None, help="Logo duration ratio filter")
        p.add_argument("--vote-frames", type=int, default=None, help="Voting frames count")
        p.add_argument("--rec-model", type=str, default=None, help="PaddleOCR recognition model name")
        p.add_argument("--det-model", type=str, default=None, help="PaddleOCR detection model name")
        p.add_argument("--roi-band", type=str, default=None, help="ROI band tuple, e.g. '0.6,1.0'")
        p.add_argument("--det-max-width", type=int, default=None, help="Detection max width downscale")
        p.add_argument("--min-box-height", type=int, default=None, help="Minimum box height in pixels")
        p.add_argument("--max-box-height", type=int, default=None, help="Maximum box height in pixels")
        p.add_argument("--line-target-height", type=int, default=None, help="Normalized line target height in pixels")
        p.add_argument("--max-side", type=int, default=None, help="Maximum crop side limit in pixels")
        p.add_argument("--min-rec-height", type=int, default=None, help="Minimum crop rec height in pixels")
        p.add_argument("--max-rec-height", type=int, default=None, help="Maximum crop rec height in pixels")
        p.add_argument("--crop-change-threshold", type=float, default=None, help="Crop change thumbnail threshold")

    common(sub.add_parser("extract", help="detect intervals and OCR text"))
    common(sub.add_parser("intervals", help="list text-present intervals only"))

    args = parser.parse_args(argv)
    try:
        from .pipeline import run_extract

        cfg_base = Config.for_mode(args.mode)
        overrides = {}
        for key in [
            "sample_fps", "scene_threshold", "iou_threshold", "sim_threshold",
            "debounce_gap", "min_duration", "conf_threshold", "logo_ratio",
            "vote_frames", "rec_model", "det_model", "det_max_width",
            "min_box_height", "max_box_height", "line_target_height",
            "max_side", "min_rec_height", "max_rec_height", "crop_change_threshold"
        ]:
            val = getattr(args, key, None)
            if val is not None:
                overrides[key] = val
        if args.roi_band is not None:
            parts = [float(x.strip()) for x in args.roi_band.split(",")]
            overrides["roi_band"] = (parts[0], parts[1])

        cfg = dataclasses.replace(cfg_base, **overrides)
        events = run_extract(args.video, cfg, start=args.start, end=args.end)
        if args.command == "intervals":
            for e in events:
                print(f"{e.start:9.2f}s - {e.end:9.2f}s  {e.text}")
            return 0
        out = export(events, args.format)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
        else:
            sys.stdout.write(out + "\n")
        return 0
    except ImportError as exc:
        print(exc, file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
