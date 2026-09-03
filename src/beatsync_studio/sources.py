from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .media import require_executable
from .models import VIDEO_EXTENSIONS

BV_PATTERN = re.compile(r"(?i)(BV[0-9A-Za-z]{10})")


def discover_local_videos(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"Video directory does not exist: {directory}")
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def normalize_bilibili_input(value: str) -> tuple[str, str]:
    match = BV_PATTERN.search(value)
    if not match:
        raise ValueError(f"Not a valid BV id or Bilibili URL: {value}")
    bv = match.group(1)
    page = None
    if "://" in value:
        raw_page = parse_qs(urlparse(value).query).get("p", [None])[0]
        if raw_page is not None:
            try:
                page = int(raw_page)
            except ValueError as exc:
                raise ValueError(f"Invalid Bilibili page number: {raw_page}") from exc
            if page < 1:
                raise ValueError("Bilibili page number must be at least 1")
    source_id = f"{bv}_p{page}" if page else bv
    url = f"https://www.bilibili.com/video/{bv}"
    if page:
        url += f"?p={page}"
    return source_id, url


class BilibiliDownloader:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "yt-dlp was not found in PATH. Install with: pip install -e .[online]"
            )
        self.command = [sys.executable, "-m", "yt_dlp"]

    def download_proxy(self, value: str) -> tuple[str, str, Path]:
        bv, url = normalize_bilibili_input(value)
        path = self._download(
            url,
            bv=bv,
            label="proxy",
            format_selector="bv*[height<=?480]+ba/b[height<=?480]/b",
            sort="res:480,+size",
        )
        return bv, url, path

    def download_master(self, value: str) -> tuple[str, str, Path]:
        bv, url = normalize_bilibili_input(value)
        path = self._download(
            url,
            bv=bv,
            label="master",
            format_selector="bv*+ba/b",
            sort=None,
        )
        return bv, url, path

    def _download(
        self,
        url: str,
        *,
        bv: str,
        label: str,
        format_selector: str,
        sort: str | None,
    ) -> Path:
        output_template = str(self.work_dir / f"{bv}_{label}.%(ext)s")
        command = [
            *self.command,
            "--no-playlist",
            "--windows-filenames",
            "--no-progress",
            "--merge-output-format",
            "mp4/mkv",
            "--ffmpeg-location",
            require_executable("ffmpeg"),
            "-f",
            format_selector,
            "-o",
            output_template,
        ]
        if sort:
            command += ["-S", sort]
        command.append(url)
        subprocess.run(command, check=True)
        matches = sorted(self.work_dir.glob(f"{bv}_{label}.*"))
        media = [item for item in matches if item.suffix.lower() in VIDEO_EXTENSIONS]
        if not media:
            raise RuntimeError(f"yt-dlp completed but no media file was found for {bv}")
        return media[0]
