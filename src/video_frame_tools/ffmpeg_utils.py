from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image


@dataclass(frozen=True)
class CropSpec:
    x: int
    y: int
    width: int
    height: int

    def to_ffmpeg_filter(self) -> str:
        return f"crop={self.width}:{self.height}:{self.x}:{self.y}"


def build_video_filter(crop: Optional[CropSpec] = None, frame_step: int = 1, start_frame: int = 1) -> str | None:
    if frame_step < 1:
        raise ValueError("frame_step must be 1 or greater.")
    if start_frame < 1:
        raise ValueError("start_frame uses 1-based indexing and must be 1 or greater.")

    filters: list[str] = []
    if crop is not None:
        filters.append(crop.to_ffmpeg_filter())
    if frame_step > 1 or start_frame > 1:
        start_index = start_frame - 1
        filters.append(f"select='not(mod(n-{start_index},{frame_step}))'")

    return ",".join(filters) if filters else None


def ensure_ffmpeg() -> None:
    if resolve_ffmpeg_executable() is None:
        raise RuntimeError(
            "ffmpeg was not found on PATH and no bundled fallback is available. "
            "Install ffmpeg and try again."
        )


def resolve_ffmpeg_executable() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg is not None:
        return system_ffmpeg

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except Exception:
        return None

    try:
        bundled = get_ffmpeg_exe()
    except Exception:
        return None

    return bundled if bundled else None


def run_ffmpeg(command: list[str]) -> None:
    ffmpeg_exe = resolve_ffmpeg_executable()
    if ffmpeg_exe is None:
        ensure_ffmpeg()
    else:
        command = [ffmpeg_exe if part == "ffmpeg" else part for part in command]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(
            "ffmpeg failed.\n"
            f"Command: {' '.join(command)}\n"
            f"stderr:\n{stderr}"
        )


def extract_reference_frame(video_path: Path, frame_path: Path) -> None:
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(frame_path),
    ]
    run_ffmpeg(command)


def get_image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def extract_frames_to_png(
    video_path: Path,
    output_dir: Path,
    crop: Optional[CropSpec] = None,
    max_frames: Optional[int] = None,
    frame_step: int = 1,
    start_frame: int = 1,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%06d.png"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
    ]
    video_filter = build_video_filter(crop=crop, frame_step=frame_step, start_frame=start_frame)
    if video_filter is not None:
        command += ["-vf", video_filter]
    if max_frames is not None:
        command += ["-frames:v", str(max_frames)]
    command += [
        "-vsync",
        "0",
        str(pattern),
    ]
    run_ffmpeg(command)
    return sorted(output_dir.glob("frame_*.png"))
