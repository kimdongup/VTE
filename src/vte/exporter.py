from __future__ import annotations

import json

from .models import TextEvent


def _ts_srt(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_ass(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def to_srt(events: list[TextEvent]) -> str:
    lines = []
    for i, e in enumerate(events, 1):
        lines.append(str(i))
        lines.append(f"{_ts_srt(e.start)} --> {_ts_srt(e.end)}")
        lines.append(e.text)
        lines.append("")
    return "\n".join(lines)


def to_txt(events: list[TextEvent]) -> str:
    return "\n".join(e.text for e in events)


def to_json(events: list[TextEvent]) -> str:
    payload = [
        {
            "start": round(e.start, 3),
            "end": round(e.end, 3),
            "text": e.text,
            "confidence": round(e.confidence, 4),
            "bboxes": [list(map(float, p)) for box in e.boxes for p in box.pts],
        }
        for e in events
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_ass(events: list[TextEvent]) -> str:
    header = (
        "[Script Info]\nScriptType: v4.00+\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour\n"
        "Style: Default,NanumGothic,48,&H00FFFFFF\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    rows = [
        f"Dialogue: 0,{_ts_ass(e.start)},{_ts_ass(e.end)},Default,{e.text}"
        for e in events
    ]
    return header + "\n".join(rows) + "\n"


FORMATS = {"srt": to_srt, "txt": to_txt, "json": to_json, "ass": to_ass}


def export(events: list[TextEvent], fmt: str) -> str:
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    return FORMATS[fmt](events)
