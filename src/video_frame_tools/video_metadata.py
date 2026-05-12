from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

from .ffmpeg_utils import resolve_ffmpeg_executable


@dataclass(frozen=True)
class VideoMetadata:
    input_video: Path
    created_at: str
    file_size_bytes: int
    duration: str | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    estimated_total_frames: int | None
    video_codec: str | None
    video_bitrate: str | None
    audio_codec: str | None
    audio_info: str | None
    ffmpeg_executable: str | None

    def to_text(self, extra: dict[str, Any] | None = None) -> str:
        lines = [
            "Video Metadata",
            "==============",
            f"input_video: {self.input_video}",
            f"created_at_utc: {self.created_at}",
            f"file_size_bytes: {self.file_size_bytes}",
            f"duration: {self.duration or 'unknown'}",
            f"duration_seconds: {self.duration_seconds if self.duration_seconds is not None else 'unknown'}",
            f"frame_size: {self.width or 'unknown'}x{self.height or 'unknown'}",
            f"fps: {self.fps if self.fps is not None else 'unknown'}",
            f"estimated_total_frames: {self.estimated_total_frames if self.estimated_total_frames is not None else 'unknown'}",
            f"video_codec: {self.video_codec or 'unknown'}",
            f"video_bitrate: {self.video_bitrate or 'unknown'}",
            f"audio_codec: {self.audio_codec or 'unknown'}",
            f"audio_info: {self.audio_info or 'unknown'}",
            f"ffmpeg_executable: {self.ffmpeg_executable or 'unknown'}",
        ]
        if extra:
            lines.extend(["", "Run Summary", "==========="])
            for key, value in extra.items():
                if isinstance(value, (dict, list, tuple)):
                    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
                else:
                    rendered = str(value)
                lines.append(f"{key}: {rendered}")
        return "\n".join(lines) + "\n"


_DURATION_RE = re.compile(r"Duration:\s*(?P<duration>[^,]+)")
_VIDEO_RE = re.compile(
    r"Video:\s*(?P<codec>[^,]+),\s*(?P<format>[^,]+),\s*(?P<width>\d+)x(?P<height>\d+),\s*(?P<bitrate>[^,]+),\s*(?P<fps>[0-9.]+)\s*fps"
)
_AUDIO_RE = re.compile(r"Audio:\s*(?P<codec>[^,]+),\s*(?P<rest>.+)")


def _parse_duration_to_seconds(duration: str | None) -> float | None:
    if not duration:
        return None
    try:
        hours, minutes, seconds = duration.split(":")
        return float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds)
    except Exception:
        return None


def probe_video_metadata(video_path: Path) -> VideoMetadata:
    ffmpeg_executable = resolve_ffmpeg_executable()
    if ffmpeg_executable is None:
        raise RuntimeError("ffmpeg was not found on PATH and no bundled fallback is available.")

    completed = subprocess.run(
        [ffmpeg_executable, "-hide_banner", "-i", str(video_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    stderr = completed.stderr

    duration = None
    width = None
    height = None
    fps = None
    video_codec = None
    video_bitrate = None
    audio_codec = None
    audio_info = None

    duration_match = _DURATION_RE.search(stderr)
    if duration_match:
        duration = duration_match.group("duration").strip()

    video_match = _VIDEO_RE.search(stderr)
    if video_match:
        video_codec = video_match.group("codec").strip()
        width = int(video_match.group("width"))
        height = int(video_match.group("height"))
        video_bitrate = video_match.group("bitrate").strip()
        fps = float(video_match.group("fps"))

    audio_match = _AUDIO_RE.search(stderr)
    if audio_match:
        audio_codec = audio_match.group("codec").strip()
        audio_info = audio_match.group("rest").strip()

    duration_seconds = _parse_duration_to_seconds(duration)
    estimated_total_frames = None
    if duration_seconds is not None and fps is not None:
        estimated_total_frames = int(round(duration_seconds * fps))

    stat = video_path.stat()
    return VideoMetadata(
        input_video=video_path,
        created_at=datetime.now(timezone.utc).isoformat(),
        file_size_bytes=stat.st_size,
        duration=duration,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
        estimated_total_frames=estimated_total_frames,
        video_codec=video_codec,
        video_bitrate=video_bitrate,
        audio_codec=audio_codec,
        audio_info=audio_info,
        ffmpeg_executable=ffmpeg_executable,
    )
