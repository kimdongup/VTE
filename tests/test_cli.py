"""CLI 단위 테스트 (pipeline은 mock, 파일 I/O 없이 메모리로)."""
from __future__ import annotations

import json
import re
from unittest import mock

from vte.cli import main
from vte.models import TextBox, TextEvent


def _events():
    pts = [(40.0, 300.0), (600.0, 300.0), (600.0, 346.0), (40.0, 346.0)]
    return [
        TextEvent(0.0, 3.0, "첫번째 자막", [TextBox(pts, 0.98)], 0.98),
        TextEvent(4.0, 7.0, "두번째 자막", [TextBox(pts, 0.97)], 0.97),
    ]


def test_extract_json_stdout(capsys):
    with mock.patch("vte.pipeline.run_extract", return_value=_events()):
        code = main(["extract", "fake.mp4", "--format", "json"])

    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert isinstance(payload, list) and len(payload) == 2
    assert [item["text"] for item in payload] == ["첫번째 자막", "두번째 자막"]
    for item in payload:
        assert set(item) == {"start", "end", "text", "confidence", "bboxes"}


def test_missing_file_returns_1(capsys):
    code = main(["extract", "/nonexistent/no_such_file.mp4", "--format", "json"])
    assert code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""


def test_intervals_stdout(capsys):
    with mock.patch("vte.pipeline.run_extract", return_value=_events()):
        code = main(["intervals", "fake.mp4"])

    assert code == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2

    # "  0.00s -      3.00s  첫번째 자막" 형식: 시작/종료 시각 + 텍스트
    ts_pattern = re.compile(r"\d+\.\d{2}s\s*-\s*\d+\.\d{2}s")
    for ln, ev in zip(lines, _events()):
        assert ts_pattern.search(ln), f"bad interval format: {ln!r}"
        assert ev.text in ln


def test_custom_cli_arguments_override_config(capsys):
    captured_cfg = []

    def mock_extract(video, cfg, start, end):
        captured_cfg.append(cfg)
        return _events()

    with mock.patch("vte.pipeline.run_extract", side_effect=mock_extract):
        code = main([
            "extract", "fake.mp4",
            "--mode", "fast",
            "--logo-ratio", "0.95",
            "--line-target-height", "64",
            "--max-box-height", "500",
            "--roi-band", "0.5, 1.0"
        ])

    assert code == 0
    assert len(captured_cfg) == 1
    cfg = captured_cfg[0]
    assert cfg.logo_ratio == 0.95
    assert cfg.line_target_height == 64
    assert cfg.max_box_height == 500
    assert cfg.roi_band == (0.5, 1.0)

