from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

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

        timestamp = 0.0
        sampled_frames = 0
        matches: list[MatchSample] = []
        next_progress = 10
        while timestamp < duration:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
            ok, frame = capture.read()
            if not ok:
                timestamp += sample_interval
                continue
            sampled_frames += 1
            frame = _resize_for_analysis(frame, max_frame_width, cv2)
            similarity = matcher.best_similarity(frame)
            if similarity is not None and similarity >= threshold:
                matches.append(MatchSample(timestamp=round(timestamp, 3), similarity=similarity))
            timestamp += sample_interval
            percent = min(100, int(timestamp / duration * 100))
            if progress_callback is not None and percent >= next_progress:
                progress_callback(next_progress)
                next_progress += 10
    finally:
        capture.release()

    segments = merge_match_samples(
        matches,
        max_gap=max_gap,
        padding=padding,
        duration=duration,
        sample_interval=sample_interval,
    )
    return duration, sampled_frames, matches, segments
