from types import SimpleNamespace

import pytest

from beatsync_studio.scanner import scan_video


class Capture:
    def __init__(self, *args):
        self.timestamp = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return 1 if prop == 1 else 10

    def set(self, prop, value):
        self.timestamp = value / 1000

    def read(self):
        return True, SimpleNamespace(shape=(100, 100), timestamp=self.timestamp)

    def release(self):
        self.released = True


class Matcher:
    def __init__(self, fail=None):
        self.cache_identity = {"engine": "test", "embedding": "a"}
        self.calls = []
        self.fail = fail

    def best_similarity(self, frame):
        if len(self.calls) == self.fail:
            raise RuntimeError("interrupted")
        self.calls.append(frame.timestamp)
        return 0.95 if 3 <= frame.timestamp <= 5 else None


@pytest.fixture
def run(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(
            VideoCapture=Capture,
            CAP_PROP_FPS=1,
            CAP_PROP_FRAME_COUNT=2,
            CAP_PROP_POS_MSEC=3,
        ),
    )
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    def scan(matcher, **kwargs):
        options = {
            "threshold": 0.9,
            "sample_interval": 2,
            "max_gap": 2.5,
            "padding": 0,
            "max_frame_width": 640,
            "cache_path": tmp_path / "cache.sqlite3",
        }
        options.update(kwargs)
        return scan_video(video, matcher, **options)

    return scan, video


def test_resume_and_recompute_intervals(run):
    scan, _ = run
    interrupted = Matcher(fail=2)
    with pytest.raises(RuntimeError, match="interrupted"):
        scan(interrupted)
    resumed = Matcher()
    result = scan(resumed)
    assert resumed.calls == [4, 6, 8]
    assert result[1] == 5
    cached = Matcher()
    changed = scan(cached, padding=1, threshold=0.8)
    assert cached.calls == []
    assert changed[3][0].start < result[3][0].start


def test_content_and_identity_invalidate(run):
    scan, video = run
    scan(Matcher())
    video.write_bytes(b"other")
    changed = Matcher()
    scan(changed)
    assert len(changed.calls) == 5
    changed = Matcher()
    changed.cache_identity = {"engine": "test", "embedding": "b"}
    scan(changed)
    assert len(changed.calls) == 5


def test_refinement_reuses_coarse_and_filters_stale_samples(run):
    scan, _ = run
    matcher = Matcher()
    result = scan(matcher, refine_interval=0.5, refine_window=2)
    assert len(matcher.calls) == len(set(matcher.calls))
    assert result[3][0].start == 2.75
    assert result[3][0].end == 5.25
    cached = Matcher()
    scan(cached, refine_interval=0.5, refine_window=2)
    assert cached.calls == []
    coarse = scan(cached)
    assert coarse[1] == 5
    assert coarse[2][0].timestamp == 4


def test_cache_disabled(run):
    scan, _ = run
    matcher = Matcher()
    scan(matcher, cache_path=None)
    scan(matcher, cache_path=None)
    assert len(matcher.calls) == 10
