from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .media import export_segments
from .models import VideoResult
from .scanner import scan_video


@dataclass(frozen=True)
class ScanOptions:
    threshold: float = 0.50
    sample_interval: float = 1.0
    max_gap: float = 2.5
    padding: float = 1.5
    max_frame_width: int = 640
    clip_mode: str = "accurate"
    export: bool = True


def process_video(
    analyzed_path: Path,
    matcher: object,
    output_dir: Path,
    options: ScanOptions,
    *,
    source_id: str,
    source_kind: str,
    source: str,
    master_path: Path | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> VideoResult:
    duration, sampled, matches, segments = scan_video(
        analyzed_path,
        matcher,
        threshold=options.threshold,
        sample_interval=options.sample_interval,
        max_gap=options.max_gap,
        padding=options.padding,
        max_frame_width=options.max_frame_width,
        progress_callback=progress_callback,
    )
    effective_master = master_path or analyzed_path
    clips: list[str] = []
    if options.export and segments:
        clips = [
            str(path.resolve())
            for path in export_segments(
                effective_master,
                segments,
                output_dir / "clips",
                clip_mode=options.clip_mode,
            )
        ]
    return VideoResult(
        source_id=source_id,
        source_kind=source_kind,
        source=source,
        analyzed_path=str(analyzed_path.resolve()),
        master_path=str(effective_master.resolve()),
        duration=duration,
        sampled_frames=sampled,
        matched_frames=len(matches),
        segments=segments,
        clips=clips,
    )


def write_manifest(output_dir: Path, results: list[VideoResult], options: ScanOptions) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "manifest.json"
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "options": {
            "threshold": options.threshold,
            "sample_interval": options.sample_interval,
            "max_gap": options.max_gap,
            "padding": options.padding,
            "max_frame_width": options.max_frame_width,
            "clip_mode": options.clip_mode,
            "export": options.export,
        },
        "summary": {
            "videos": len(results),
            "videos_with_matches": sum(bool(item.segments) for item in results),
            "segments": sum(len(item.segments) for item in results),
            "clips": sum(len(item.clips) for item in results),
            "errors": sum(bool(item.error) for item in results),
        },
        "results": [item.to_dict() for item in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
