from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MatchSample:
    timestamp: float
    similarity: float


@dataclass(frozen=True)
class TimeSegment:
    start: float
    end: float
    peak_similarity: float
    sample_count: int

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class VideoResult:
    source_id: str
    source_kind: str
    source: str
    analyzed_path: str
    master_path: str | None
    duration: float
    sampled_frames: int
    matched_frames: int
    segments: list[TimeSegment] = field(default_factory=list)
    clips: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


VIDEO_EXTENSIONS = {
    ".avi",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ts",
    ".webm",
}


def safe_stem(path: Path) -> str:
    allowed = {"-", "_", "."}
    value = "".join(c if c.isalnum() or c in allowed else "_" for c in path.stem)
    return value.strip("._") or "video"
