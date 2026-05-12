from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image


VALID_CHANNELS = ("red", "green", "blue", "gray")


def normalize_channels(requested: Iterable[str]) -> list[str]:
    channels = []
    for channel in requested:
        lowered = channel.lower()
        if lowered == "all":
            return list(VALID_CHANNELS)
        if lowered not in VALID_CHANNELS:
            raise ValueError(
                f"Unsupported channel '{channel}'. Choose from: {', '.join(VALID_CHANNELS)}"
            )
        if lowered not in channels:
            channels.append(lowered)
    if not channels:
        raise ValueError("At least one channel must be requested.")
    return channels


def channel_image(image: Image.Image, channel: str) -> Image.Image:
    rgb = image.convert("RGB")
    array = np.asarray(rgb, dtype=np.uint8)

    if channel == "gray":
        return rgb.convert("L")

    index_map = {"red": 0, "green": 1, "blue": 2}
    if channel not in index_map:
        raise ValueError(f"Unsupported channel '{channel}'.")
    return Image.fromarray(array[:, :, index_map[channel]]).convert("L")


def save_channel_exports(
    source_path: Path,
    output_dir: Path,
    channels: Iterable[str],
) -> dict[str, Path]:
    channel_list = normalize_channels(channels)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, Path] = {}
    with Image.open(source_path) as image:
        for channel in channel_list:
            channel_dir = output_dir / channel
            channel_dir.mkdir(parents=True, exist_ok=True)
            out_path = channel_dir / source_path.name
            channel_image(image, channel).save(out_path, format="PNG")
            saved[channel] = out_path
    return saved
