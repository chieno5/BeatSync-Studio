from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from . import __version__
from .face import FaceMatcher
from .media import export_segments, require_executable
from .models import VideoResult
from .pipeline import ScanOptions, process_video, write_manifest
from .sources import BilibiliDownloader, discover_local_videos, normalize_bilibili_input


def _print_scan_progress(percent: int) -> None:
    print(f"  Scan progress: {percent}%", flush=True)


def _add_scan_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--reference", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--engine", choices=("real", "anime"), default="real")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--max-gap", type=float, default=2.5)
    parser.add_argument("--padding", type=float, default=1.5)
    parser.add_argument("--max-frame-width", type=int, default=640)
    parser.add_argument("--clip-mode", choices=("accurate", "copy"), default="accurate")
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--refine-interval", type=float)
    parser.add_argument("--refine-window", type=float, default=4.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="beatsync", description="Find a target face in videos")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check required and optional runtime dependencies")

    local = subparsers.add_parser("scan-local", help="Scan all videos under a local directory")
    _add_scan_options(local)
    local.add_argument("--videos-dir", required=True, type=Path)

    online = subparsers.add_parser("scan-bv", help="Scan one or more Bilibili BV videos")
    _add_scan_options(online)
    online.add_argument("--bv", action="append", required=True)
    online.add_argument("--keep-downloads", action="store_true")
    return parser


def _options(args: argparse.Namespace) -> ScanOptions:
    threshold = (
        args.threshold if args.threshold is not None else (0.88 if args.engine == "anime" else 0.50)
    )
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("--threshold must be between 0 and 1")
    if args.sample_interval <= 0 or args.max_gap < 0 or args.padding < 0:
        raise ValueError("Sampling interval must be positive; gap and padding cannot be negative")
    if args.refine_interval is not None and not 0 < args.refine_interval <= args.sample_interval:
        raise ValueError("--refine-interval must be positive and no larger than --sample-interval")
    if args.refine_window < 0:
        raise ValueError("--refine-window cannot be negative")
    if args.max_frame_width < 128:
        raise ValueError("--max-frame-width must be at least 128")
    return ScanOptions(
        threshold=threshold,
        sample_interval=args.sample_interval,
        max_gap=args.max_gap,
        padding=args.padding,
        max_frame_width=args.max_frame_width,
        clip_mode=args.clip_mode,
        export=not args.no_export,
        cache=not args.no_cache,
        refine_interval=args.refine_interval,
        refine_window=args.refine_window,
    )


def _validate_references(paths: list[Path]) -> list[Path]:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise ValueError("Reference image does not exist: " + ", ".join(map(str, missing)))
    return paths


def _create_matcher(engine: str, references: list[Path]):
    if engine == "anime":
        from .anime import AnimeCharacterMatcher

        return AnimeCharacterMatcher(references)
    return FaceMatcher(references)


def doctor() -> int:
    try:
        ffmpeg_available = bool(require_executable("ffmpeg"))
    except RuntimeError:
        ffmpeg_available = False
    checks = {
        "Python 3.10-3.12": (3, 10) <= sys.version_info[:2] < (3, 13),
        "FFmpeg": ffmpeg_available,
        "yt-dlp (online mode)": importlib.util.find_spec("yt_dlp") is not None,
        "onnxruntime (anime mode)": importlib.util.find_spec("onnxruntime") is not None,
        "cv2": importlib.util.find_spec("cv2") is not None,
        "numpy": importlib.util.find_spec("numpy") is not None,
    }
    for name, ok in checks.items():
        print(f"[{'OK' if ok else 'MISSING'}] {name}")
    required = [
        checks[name]
        for name in (
            "Python 3.10-3.12",
            "FFmpeg",
            "yt-dlp (online mode)",
            "onnxruntime (anime mode)",
            "cv2",
            "numpy",
        )
    ]
    if not all(required):
        print("\nFix: run the setup script again, then retry 'beatsync doctor'.")
    return 0 if all(required) else 1


def scan_local(args: argparse.Namespace) -> int:
    options = _options(args)
    references = _validate_references(args.reference)
    videos = discover_local_videos(args.videos_dir)
    if not videos:
        raise ValueError(f"No supported videos found under: {args.videos_dir}")
    matcher = _create_matcher(args.engine, references)
    print(f"Face provider: {matcher.providers[0]}")
    results: list[VideoResult] = []
    for index, video in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] Scanning {video}")
        try:
            result = process_video(
                video,
                matcher,
                args.output_dir,
                options,
                source_id=str(video.resolve()),
                source_kind="local",
                source=str(video.resolve()),
                progress_callback=_print_scan_progress,
            )
        except Exception as exc:  # noqa: BLE001 - isolate failures in a video batch
            result = VideoResult(
                source_id=str(video.resolve()),
                source_kind="local",
                source=str(video.resolve()),
                analyzed_path=str(video.resolve()),
                master_path=str(video.resolve()),
                duration=0.0,
                sampled_frames=0,
                matched_frames=0,
                error=str(exc),
            )
            print(f"  ERROR: {exc}")
        else:
            print(f"  {len(result.segments)} segment(s), {len(result.clips)} clip(s)")
        results.append(result)
        write_manifest(args.output_dir, results, options)
    print(f"Manifest: {(args.output_dir / 'manifest.json').resolve()}")
    return 0


def scan_bv(args: argparse.Namespace) -> int:
    options = _options(args)
    references = _validate_references(args.reference)
    matcher = _create_matcher(args.engine, references)
    downloader = BilibiliDownloader(args.output_dir / "work")
    print(f"Face provider: {matcher.providers[0]}")
    results: list[VideoResult] = []
    for index, value in enumerate(args.bv, start=1):
        bv, url = normalize_bilibili_input(value)
        print(f"[{index}/{len(args.bv)}] Downloading proxy for {bv}")
        proxy: Path | None = None
        master: Path | None = None
        try:
            _, _, proxy = downloader.download_proxy(value)
            probe_options = ScanOptions(**{**options.__dict__, "export": False})
            probe = process_video(
                proxy,
                matcher,
                args.output_dir,
                probe_options,
                source_id=bv,
                source_kind="bilibili",
                source=url,
                progress_callback=_print_scan_progress,
            )
            if probe.segments and options.export:
                print(f"  Match found; downloading master for {bv}")
                _, _, master = downloader.download_master(value)
                probe.master_path = str(master.resolve())
                probe.clips = [
                    str(path.resolve())
                    for path in export_segments(
                        master,
                        probe.segments,
                        args.output_dir / "clips",
                        clip_mode=options.clip_mode,
                    )
                ]
            result = probe
            print(f"  {len(result.segments)} segment(s), {len(result.clips)} clip(s)")
        except Exception as exc:  # noqa: BLE001 - preserve a manifest entry on any failure
            result = VideoResult(
                source_id=bv,
                source_kind="bilibili",
                source=url,
                analyzed_path=str(proxy.resolve()) if proxy else "",
                master_path=str(master.resolve()) if master else None,
                duration=0.0,
                sampled_frames=0,
                matched_frames=0,
                error=str(exc),
            )
            print(f"  ERROR: {exc}")
        finally:
            if not args.keep_downloads:
                for path in (proxy, master):
                    if path and path.is_file():
                        path.unlink()
        results.append(result)
        write_manifest(args.output_dir, results, options)
    print(f"Manifest: {(args.output_dir / 'manifest.json').resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor()
        if args.command == "scan-local":
            return scan_local(args)
        if args.command == "scan-bv":
            return scan_bv(args)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2
