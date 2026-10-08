from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cache import AnalysisCache, analysis_key
from .intervals import merge_match_samples
from .models import MatchSample, TimeSegment


def _resize_for_analysis(frame: Any, max_width: int, cv2: Any) -> Any:
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame
    ratio = max_width / width
    return cv2.resize(frame, (max_width, max(1, int(height * ratio))), interpolation=cv2.INTER_AREA)


def scan_video(
    path: Path,
    matcher: Any,
    *,
    threshold: float,
    sample_interval: float,
    max_gap: float,
    padding: float,
    max_frame_width: int,
    cache_path: Path | None = None,
    refine_interval: float | None = None,
    refine_window: float = 4.0,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[float, int, list[MatchSample], list[TimeSegment]]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is missing. Install the project with: pip install -e .") from exc

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        duration = frames / fps if fps > 0 and frames > 0 else 0.0
        if duration <= 0:
            raise ValueError(f"Cannot determine video duration: {path}")

        if sample_interval <= 0 or (refine_interval is not None and refine_interval <= 0):
            raise ValueError("Sampling intervals must be positive")
        if refine_window < 0:
            raise ValueError("Refine window cannot be negative")
        cache = (
            AnalysisCache(cache_path, analysis_key(path, matcher, max_frame_width))
            if cache_path is not None
            else None
        )
        try:
            scores = cache.load() if cache else {}
            visited: dict[int, tuple[bool, float | None]] = {}
            next_progress = 10

            def evaluate(timestamp: float) -> None:
                key = round(timestamp * 1_000_000)
                if key in visited:
                    return
                if key not in scores:
                    capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
                    ok, frame = capture.read()
                    similarity = (
                        matcher.best_similarity(_resize_for_analysis(frame, max_frame_width, cv2))
                        if ok
                        else None
                    )
                    scores[key] = (bool(ok), similarity)
                    if cache:
                        cache.save(key, bool(ok), similarity)
                visited[key] = scores[key]

            index = 0
            while index * sample_interval < duration:
                timestamp = index * sample_interval
                evaluate(timestamp)
                index += 1
                percent = min(100, int(index * sample_interval / duration * 100))
                while progress_callback is not None and percent >= next_progress:
                    progress_callback(next_progress)
                    next_progress += 10

            if refine_interval is not None:
                coarse_hits = [
                    key / 1_000_000
                    for key, (_, score) in visited.items()
                    if score is not None and score >= threshold
                ]
                windows: list[list[float]] = []
                for hit in sorted(coarse_hits):
                    start, end = max(0.0, hit - refine_window), min(duration, hit + refine_window)
                    if windows and start <= windows[-1][1]:
                        windows[-1][1] = max(windows[-1][1], end)
                    else:
                        windows.append([start, end])
                for start, end in windows:
                    index = 0
                    while start + index * refine_interval <= end:
                        timestamp = start + index * refine_interval
                        if timestamp < duration:
                            evaluate(timestamp)
                        index += 1

            sampled_frames = sum(decoded for decoded, _ in visited.values())
            matches = [
                MatchSample(timestamp=key / 1_000_000, similarity=score)
                for key, (_, score) in sorted(visited.items())
                if score is not None and score >= threshold
            ]
        finally:
            if cache:
                cache.close()
    finally:
        capture.release()

    segments = merge_match_samples(
        matches,
        max_gap=max_gap,
        padding=padding,
        duration=duration,
        sample_interval=refine_interval or sample_interval,
    )
    return duration, sampled_frames, matches, segments
