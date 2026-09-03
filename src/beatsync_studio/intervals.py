from __future__ import annotations

from collections.abc import Iterable

from .models import MatchSample, TimeSegment


def merge_overlapping_segments(segments: Iterable[TimeSegment]) -> list[TimeSegment]:
    """Merge overlapping or touching intervals after padding has been applied."""
    ordered = sorted(segments, key=lambda item: item.start)
    if not ordered:
        return []
    merged = [ordered[0]]
    for segment in ordered[1:]:
        previous = merged[-1]
        if segment.start <= previous.end:
            merged[-1] = TimeSegment(
                start=previous.start,
                end=max(previous.end, segment.end),
                peak_similarity=max(previous.peak_similarity, segment.peak_similarity),
                sample_count=previous.sample_count + segment.sample_count,
            )
        else:
            merged.append(segment)
    return merged


def merge_match_samples(
    samples: Iterable[MatchSample],
    *,
    max_gap: float,
    padding: float,
    duration: float,
    sample_interval: float,
) -> list[TimeSegment]:
    """Merge matching samples into bounded video intervals."""
    if max_gap < 0 or padding < 0 or sample_interval <= 0:
        raise ValueError("max_gap/padding must be non-negative and sample_interval positive")
    ordered = sorted(samples, key=lambda item: item.timestamp)
    if not ordered:
        return []

    groups: list[list[MatchSample]] = [[ordered[0]]]
    for sample in ordered[1:]:
        if sample.timestamp - groups[-1][-1].timestamp <= max_gap:
            groups[-1].append(sample)
        else:
            groups.append([sample])

    tail = sample_interval / 2.0
    result: list[TimeSegment] = []
    for group in groups:
        start = max(0.0, group[0].timestamp - tail - padding)
        end = min(duration, group[-1].timestamp + tail + padding)
        if end > start:
            result.append(
                TimeSegment(
                    start=round(start, 3),
                    end=round(end, 3),
                    peak_similarity=max(item.similarity for item in group),
                    sample_count=len(group),
                )
            )
    return merge_overlapping_segments(result)
