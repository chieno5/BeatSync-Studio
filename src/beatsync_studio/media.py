from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import TimeSegment, safe_stem


def require_executable(name: str) -> str:
    value = shutil.which(name)
    if value:
        return value
    if name == "ffmpeg":
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            return get_ffmpeg_exe()
        except (ImportError, RuntimeError) as exc:
            raise RuntimeError(
                "FFmpeg is unavailable. Re-run the project installer or install imageio-ffmpeg."
            ) from exc
    raise RuntimeError(f"Required executable '{name}' was not found in PATH")


def export_segments(
    video: Path,
    segments: list[TimeSegment],
    output_dir: Path,
    *,
    clip_mode: str,
) -> list[Path]:
    ffmpeg = require_executable("ffmpeg")
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for index, segment in enumerate(segments, start=1):
        filename = f"{safe_stem(video)}_{index:04d}_{segment.start:.3f}-{segment.end:.3f}.mp4"
        destination = output_dir / filename
        duration = segment.end - segment.start
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{segment.start:.3f}",
            "-i",
            str(video),
            "-t",
            f"{duration:.3f}",
        ]
        if clip_mode == "copy":
            command += ["-map", "0", "-c", "copy", "-avoid_negative_ts", "make_zero"]
        else:
            command += [
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
            ]
        command.append(str(destination))
        subprocess.run(command, check=True)
        exported.append(destination)
    return exported
