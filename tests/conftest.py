from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fixtures.make_synth_video import make_synth


@pytest.fixture
def synth_video(tmp_path):
    """tmp_path에 합성 자막 영상을 만들어 경로를 반환 (저장소 오염 없음)."""
    path = tmp_path / "synth.mp4"
    make_synth(str(path))
    return str(path)
