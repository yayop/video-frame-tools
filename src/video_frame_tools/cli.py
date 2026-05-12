from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from . import __version__
from .browser_roi import select_roi_in_browser
from .ffmpeg_utils import CropSpec, extract_frames_to_png, extract_reference_frame, get_image_size
from .image_ops import normalize_channels, save_channel_exports
from .roi_selector import ROI, load_roi, select_roi_from_video
from .video_metadata import probe_video_metadata


def _resolve_trim_crop(reference_frame: Path, trim_sides: int, trim_top: int, trim_bottom: int) -> CropSpec:
    width, height = get_image_size(reference_frame)
    x = trim_sides
    y = trim_top
    right = trim_sides
    bottom = trim_bottom
    crop_width = width - x - right
    crop_height = height - y - bottom
    if crop_width <= 0 or crop_height <= 0:
        raise ValueError("Trim values remove the entire frame.")
    return CropSpec(x=x, y=y, width=crop_width, height=crop_height)


def _default_output_dir(video_path: Path) -> Path:
    return video_path.with_suffix("")


def _default_roi_path(video_path: Path) -> Path:
    return _default_output_dir(video_path) / "roi.json"


def _default_report_path(video_path: Path) -> Path:
    return _default_output_dir(video_path) / "video_metadata.txt"


def _validate_roi_for_video(video_path: Path, roi: ROI) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        reference = Path(tmpdir) / "reference.png"
        extract_reference_frame(video_path, reference)
        width, height = get_image_size(reference)

    if (width, height) != (roi.frame_width, roi.frame_height):
        raise ValueError(
            "ROI resolution does not match this video. "
            f"ROI expects {roi.frame_width}x{roi.frame_height}, "
            f"but the video is {width}x{height}."
        )


def _save_manifest(
    output_dir: Path,
    input_video: Path,
    crop: CropSpec | None,
    channels: Iterable[str],
    frame_count: int,
    keep_source: bool,
    workers: int,
) -> None:
    manifest = {
        "tool": "video-frame-tools",
        "version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_video": str(input_video),
        "crop": asdict(crop) if crop is not None else None,
        "channels": list(channels),
        "frame_count": frame_count,
        "keep_source": keep_source,
        "workers": workers,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _save_video_report(report_path: Path, video_path: Path, extra: dict[str, object] | None = None) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = probe_video_metadata(video_path)
    report_path.write_text(metadata.to_text(extra=extra), encoding="utf-8")


def cmd_roi(args: argparse.Namespace) -> int:
    video_path = Path(args.video)
    output = Path(args.output) if args.output is not None else _default_roi_path(video_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    reference = output.parent / "reference_frame.png"
    print(f"Writing reference frame to: {reference}", file=sys.stderr)
    if args.tk:
        print("Opening Tk ROI selector. If it is not visible, check behind the terminal or open the reference PNG.", file=sys.stderr)
        roi = select_roi_from_video(video_path, output, reference_path=reference)
    else:
        print("Opening browser ROI selector. Draw a rectangle and click Save ROI.", file=sys.stderr)
        roi = select_roi_in_browser(video_path, output, reference_path=reference)
    _save_video_report(
        output.parent / "video_metadata.txt",
        video_path,
        extra={
            "roi_json": str(output),
            "selected_roi": {
                "x": roi.x,
                "y": roi.y,
                "width": roi.width,
                "height": roi.height,
                "frame_width": roi.frame_width,
                "frame_height": roi.frame_height,
            },
        },
    )
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    video_path = Path(args.video)
    output_dir = Path(args.output_dir) if args.output_dir is not None else _default_output_dir(video_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_channels = normalize_channels(args.channels)
    if args.roi is not None and any((args.trim_sides, args.trim_top, args.trim_bottom)):
        raise ValueError("Use either --roi or trim arguments, not both.")

    crop: CropSpec | None = None
    if args.roi is not None:
        roi = load_roi(Path(args.roi))
        _validate_roi_for_video(video_path, roi)
        crop = CropSpec(roi.x, roi.y, roi.width, roi.height)
    elif any((args.trim_sides, args.trim_top, args.trim_bottom)):
        with tempfile.TemporaryDirectory() as tmpdir:
            reference = Path(tmpdir) / "reference.png"
            extract_reference_frame(video_path, reference)
            crop = _resolve_trim_crop(
                reference,
                trim_sides=int(args.trim_sides),
                trim_top=int(args.trim_top),
                trim_bottom=int(args.trim_bottom),
            )

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        frames = extract_frames_to_png(
            video_path,
            raw_dir,
            crop=crop,
            max_frames=args.max_frames,
        )

        source_dir = output_dir / "source" if args.keep_source else None
        if source_dir is not None:
            source_dir.mkdir(parents=True, exist_ok=True)

        def process_frame(frame_path: Path) -> None:
            if source_dir is not None:
                shutil.copy2(frame_path, source_dir / frame_path.name)
            save_channel_exports(frame_path, output_dir, requested_channels)

        if int(args.workers) > 1:
            with ThreadPoolExecutor(max_workers=int(args.workers)) as executor:
                list(executor.map(process_frame, frames))
        else:
            for frame_path in frames:
                process_frame(frame_path)

    _save_manifest(
        output_dir=output_dir,
        input_video=video_path,
        crop=crop,
        channels=requested_channels,
        frame_count=len(frames),
        keep_source=bool(args.keep_source),
        workers=int(args.workers),
    )
    _save_video_report(
        output_dir / "video_metadata.txt",
        video_path,
        extra={
            "output_dir": str(output_dir),
            "frames_written": len(frames),
            "channels": requested_channels,
            "workers": int(args.workers),
            "max_frames": args.max_frames,
            "keep_source": bool(args.keep_source),
            "crop": asdict(crop) if crop is not None else None,
        },
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-frames",
        description="Extract PNG frame sequences from video, crop ROI, and export per-channel grayscale images.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    roi = subparsers.add_parser("roi", help="Interactively pick a crop ROI on the first frame.")
    roi.add_argument("video", help="Input video path.")
    roi.add_argument(
        "--output",
        help="Where to write the ROI JSON. Defaults to <video-stem>_roi.json next to the video.",
    )
    roi.add_argument(
        "--tk",
        action="store_true",
        help="Use the legacy Tk ROI selector instead of the browser selector.",
    )
    roi.set_defaults(func=cmd_roi)

    extract = subparsers.add_parser("extract", help="Extract frames and export channel images.")
    extract.add_argument("video", help="Input video path.")
    extract.add_argument(
        "--output-dir",
        help="Output directory. Defaults to a sibling folder named after the video stem.",
    )
    extract.add_argument("--roi", help="ROI JSON previously saved by the roi command.")
    extract.add_argument("--trim-sides", type=int, default=0, help="Trim this many pixels from both left and right.")
    extract.add_argument("--trim-top", type=int, default=0, help="Trim this many pixels from the top.")
    extract.add_argument("--trim-bottom", type=int, default=0, help="Trim this many pixels from the bottom.")
    extract.add_argument(
        "--channels",
        nargs="+",
        default=["red", "green", "blue", "gray"],
        help="Channels to export. Use 'all' or list any of: red green blue gray.",
    )
    extract.add_argument(
        "--keep-source",
        action="store_true",
        help="Also keep the cropped source PNG frames under output-dir/source.",
    )
    extract.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker threads for per-frame channel export.",
    )
    extract.add_argument(
        "--max-frames",
        type=int,
        help="Limit extraction to the first N frames. Useful for benchmarking.",
    )
    extract.set_defaults(func=cmd_extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")
