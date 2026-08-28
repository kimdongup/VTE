"""실영상 첫 60초 골든 JSON 캡처 스크립트 (수동 1회 실행용).

pytest에서 실행하지 않는다 (실엔진 full pipeline은 수 분 소요):

    .venv/bin/python tests/golden/capture_golden.py

claude_first60s.mp4(1920x1080, 60초)를 fast 모드로 추출해
tests/golden/first60s.json에 저장한다. 메타(모델명·모드·생성일) 포함.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from vte.config import Config
from vte.pipeline import run_extract

ROOT_DIR = Path(__file__).resolve().parents[2]
_LOCAL_VIDEO = ROOT_DIR / "claude_first60s.mp4"
_FALLBACK_VIDEO = Path("/Users/mac/Downloads/my_training/claude_first60s.mp4")
VIDEO = _LOCAL_VIDEO if _LOCAL_VIDEO.exists() else _FALLBACK_VIDEO
OUT = Path(__file__).with_name("first60s.json")


def main() -> None:
    if not VIDEO.exists():
        raise SystemExit(f"샘플 영상 없음: {VIDEO}")

    cfg = Config.for_mode("fast")
    events = run_extract(str(VIDEO), cfg)

    payload = {
        "meta": {
            "video": VIDEO.name,
            "mode": "fast",
            "det_model": cfg.det_model,
            "rec_model": cfg.rec_model,
            "sample_fps": cfg.sample_fps,
            "roi_band": list(cfg.roi_band) if cfg.roi_band else None,
            "det_max_width": cfg.det_max_width,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "events": [
            {
                "start": round(e.start, 3),
                "end": round(e.end, 3),
                "text": e.text,
                "confidence": round(e.confidence, 4),
                "bboxes": [list(map(float, p)) for box in e.boxes for p in box.pts],
            }
            for e in events
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(events)} events)")
    for e in events[:10]:
        print(f"  {e.start:7.2f} ~ {e.end:7.2f}  {e.text}")


if __name__ == "__main__":
    main()
