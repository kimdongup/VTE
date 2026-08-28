import pytest

from vte.exporter import export
from vte.models import TextEvent


def sample_events():
    return [
        TextEvent(start=1.5, end=3.25, text="안녕하세요", confidence=0.97),
        TextEvent(start=10.0, end=12.0, text="두 번째 자막", confidence=1.0),
    ]


class TestSrt:
    def test_timecode_format(self):
        out = export(sample_events(), "srt")
        assert "00:00:01,500 --> 00:00:03,250" in out
        assert "00:00:10,000 --> 00:00:12,000" in out

    def test_indexing_and_text(self):
        out = export(sample_events(), "srt")
        lines = out.strip().split("\n")
        assert lines[0] == "1" and lines[4] == "2"
        assert "안녕하세요" in out

    def test_negative_clamped(self):
        e = [TextEvent(start=-0.2, end=0.5, text="x")]
        assert "-00:00:00,200" not in export(e, "srt")


class TestTxt:
    def test_lines(self):
        assert export(sample_events(), "txt").split("\n") == [
            "안녕하세요",
            "두 번째 자막",
        ]


class TestJson:
    def test_structure(self):
        import json

        data = json.loads(export(sample_events(), "json"))
        assert data[0]["start"] == 1.5
        assert data[0]["end"] == 3.25
        assert data[0]["confidence"] == pytest.approx(0.97)
        assert "bboxes" in data[0]

    def test_korean_not_escaped(self):
        assert "안녕하세요" in export(sample_events(), "json")


class TestAss:
    def test_dialogue_rows(self):
        out = export(sample_events(), "ass")
        assert "Dialogue: 0,0:00:01.50,0:00:03.25,Default,안녕하세요" in out

    def test_timecode_format_over_minute(self):
        e = [TextEvent(start=65.25, end=125.5, text="긴자막")]
        out = export(e, "ass")
        assert "Dialogue: 0,0:01:05.25,0:02:05.50,Default,긴자막" in out


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        export(sample_events(), "xml")
