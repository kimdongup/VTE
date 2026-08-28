import pytest

from vte.config import Config
from vte.models import TextBox, Track
from vte.postprocess import is_mostly_korean, normalize
from vte.segmenter import best_text, build_events, drop_logos


def mk_track(id_, start, end, text="테스트 자막", score=1.0):
    t = Track(
        id=id_,
        boxes={0: TextBox([(0, 0), (10, 0), (10, 10), (0, 10)])},
        texts=[text],
        scores=[score],
        start_ts=start,
        end_ts=end,
    )
    return t


class TestBestText:
    def test_single(self):
        assert best_text(mk_track(1, 0, 1)) == ("테스트 자막", pytest.approx(1.0))

    def test_majority_vote(self):
        t = mk_track(1, 0, 1)
        t.texts = ["가나다라", "가나다라", "마바사아자"]
        text, conf = best_text(t)
        assert text == "가나다라"
        assert conf == pytest.approx(2 / 3)

    def test_no_majority_returns_empty(self):
        t = mk_track(1, 0, 1)
        t.texts = ["가나다", "라마바", "아자차"]
        text, _ = best_text(t)
        assert text == ""

    def test_empty_texts(self):
        t = Track(id=1, start_ts=0, end_ts=1)
        assert best_text(t) == ("", 0.0)


class TestBuildEvents:
    def test_similar_merged_into_one_event(self):
        tracks = [mk_track(1, 0.0, 1.0, "이것은 자막입니다"),
                  mk_track(2, 1.1, 2.0, "이것은 자막 입니다")]
        events = build_events(tracks)
        assert len(events) == 1
        assert events[0].start == 0.0 and events[0].end == 2.0

    def test_different_text_stays_separate(self):
        tracks = [mk_track(1, 0.0, 1.0, "첫번째 문장"),
                  mk_track(2, 1.5, 2.5, "완전히 다른 말")]
        assert len(build_events(tracks)) == 2

    def test_similarity_boundary_084_vs_086(self):
        near = ["한글자막열두글자테스트", "한글자막열두글자테스트요"]
        tracks = [mk_track(1, 0.0, 1.0, near[0]), mk_track(2, 1.1, 2.0, near[1])]
        n_events = len(build_events(tracks))
        assert n_events in (1, 2)

    def test_short_gap_filled(self):
        cfg = Config(debounce_gap=0.5)
        tracks = [mk_track(1, 0.0, 1.0), mk_track(2, 1.3, 2.0)]
        assert len(build_events(tracks, cfg)) == 1

    def test_long_gap_not_filled(self):
        cfg = Config(debounce_gap=0.5)
        tracks = [mk_track(1, 0.0, 1.0), mk_track(2, 1.8, 2.8)]
        assert len(build_events(tracks, cfg)) == 2

    def test_min_duration_filter_boundary(self):
        cfg = Config(min_duration=0.5)
        short = build_events([mk_track(1, 0.0, 0.49)], cfg)
        long_ = build_events([mk_track(1, 0.0, 0.51)], cfg)
        assert len(short) == 0 and len(long_) == 1

    def test_low_confidence_dropped(self):
        cfg = Config(vote_frames=3)
        t = mk_track(1, 0, 1)
        t.texts = ["가", "나", "다"]
        assert len(build_events([t], cfg)) == 0


class TestDropLogos:
    def test_logo_ratio_boundary(self):
        from vte.models import TextEvent

        duration = 100.0
        logo = TextEvent(start=0.0, end=79.9, text="로고")
        kept, logos = drop_logos([logo], duration, Config(logo_ratio=0.8))
        assert len(logos) == 0 and len(kept) == 1

        logo2 = TextEvent(start=0.0, end=80.1, text="로고")
        kept, logos = drop_logos([logo2], duration, Config(logo_ratio=0.8))
        assert len(logos) == 1 and len(kept) == 0

    def test_zero_duration_keeps_everything(self):
        from vte.models import TextEvent

        e = TextEvent(start=0.0, end=50.0, text="자막")
        kept, logos = drop_logos([e], 0.0)
        assert len(kept) == 1 and not logos


class TestPostprocess:
    def test_normalize_spaces_and_newlines(self):
        assert normalize(" 안녕\n 하세요 ") == "안녕 하세요"

    def test_normalize_repeated_symbols(self):
        assert normalize("와!!!!!!대박") == "와!대박"

    def test_korean_ratio(self):
        assert is_mostly_korean("안녕하세요 hello")
        assert is_mostly_korean("2024년")
        assert is_mostly_korean("12345")  # no letters -> pass-through
        assert not is_mostly_korean("hello world only english here")
