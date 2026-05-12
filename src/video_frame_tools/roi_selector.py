from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox

from .ffmpeg_utils import extract_reference_frame


@dataclass(frozen=True)
class ROI:
    x: int
    y: int
    width: int
    height: int
    frame_width: int
    frame_height: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class ROISelector:
    def __init__(self, image: Image.Image, source_name: str, max_display: tuple[int, int] = (1280, 800)):
        self.image = image.convert("RGB")
        self.source_name = source_name
        self.max_display = max_display
        self.scale = self._compute_scale()
        self.display_image = self._create_display_image()
        self.selection: Optional[tuple[int, int, int, int]] = None
        self._start: Optional[tuple[int, int]] = None
        self._rect_id: Optional[int] = None

        self.root = tk.Tk()
        self.root.title("Video Frame ROI Selector")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)
        self.root.after(100, self._bring_to_front)

        header = tk.Label(
            self.root,
            text=f"Drag a rectangle on: {self.source_name}",
            anchor="w",
            justify="left",
        )
        header.pack(fill="x", padx=12, pady=(12, 4))

        self.coords_var = tk.StringVar(value="x=0 y=0 w=0 h=0")
        coords = tk.Label(self.root, textvariable=self.coords_var, anchor="w")
        coords.pack(fill="x", padx=12, pady=(0, 8))

        self.canvas = tk.Canvas(
            self.root,
            width=self.display_image.width,
            height=self.display_image.height,
            highlightthickness=1,
            highlightbackground="#444",
            cursor="crosshair",
        )
        self.canvas.pack(padx=12, pady=8)

        self.photo = ImageTk.PhotoImage(self.display_image)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        controls = tk.Frame(self.root)
        controls.pack(fill="x", padx=12, pady=(0, 12))

        tk.Button(controls, text="Reset", command=self._reset).pack(side="left")
        tk.Button(controls, text="Cancel", command=self._cancel).pack(side="right")
        tk.Button(controls, text="Save ROI", command=self._save).pack(side="right", padx=(0, 8))

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _bring_to_front(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(500, lambda: self.root.attributes("-topmost", False))

    def _compute_scale(self) -> float:
        max_width, max_height = self.max_display
        scale = min(max_width / self.image.width, max_height / self.image.height, 1.0)
        return scale

    def _create_display_image(self) -> Image.Image:
        if self.scale == 1.0:
            return self.image
        new_size = (
            max(1, int(round(self.image.width * self.scale))),
            max(1, int(round(self.image.height * self.scale))),
        )
        try:
            resampling = Image.Resampling.LANCZOS
        except AttributeError:  # pragma: no cover
            resampling = Image.LANCZOS
        return self.image.resize(new_size, resampling)

    def _display_to_image_coords(self, x: int, y: int) -> tuple[int, int]:
        if self.scale == 0:
            return x, y
        return (
            max(0, min(self.image.width, int(round(x / self.scale)))),
            max(0, min(self.image.height, int(round(y / self.scale)))),
        )

    def _clamp_selection(self, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
        left = max(0, min(x0, x1))
        top = max(0, min(y0, y1))
        right = min(self.image.width, max(x0, x1))
        bottom = min(self.image.height, max(y0, y1))
        return left, top, max(1, right - left), max(1, bottom - top)

    def _coords_text(self, selection: Optional[tuple[int, int, int, int]]) -> str:
        if selection is None:
            return "x=0 y=0 w=0 h=0"
        x, y, w, h = selection
        return f"x={x} y={y} w={w} h={h}"

    def _on_press(self, event: tk.Event) -> None:
        self._start = (event.x, event.y)
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x, event.y
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline="#00d1ff",
            width=2,
        )
        ix0, iy0 = self._display_to_image_coords(x0, y0)
        ix1, iy1 = self._display_to_image_coords(x1, y1)
        self.selection = self._clamp_selection(ix0, iy0, ix1, iy1)
        self.coords_var.set(self._coords_text(self.selection))

    def _on_release(self, event: tk.Event) -> None:
        self._on_drag(event)

    def _reset(self) -> None:
        self.selection = None
        self._start = None
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        self.coords_var.set(self._coords_text(None))

    def _cancel(self) -> None:
        self.selection = None
        self.root.destroy()

    def _save(self) -> None:
        if self.selection is None:
            messagebox.showwarning("ROI selector", "Select a rectangle before saving.")
            return
        self.root.destroy()

    def run(self) -> Optional[ROI]:
        self.root.mainloop()
        if self.selection is None:
            return None
        x, y, w, h = self.selection
        return ROI(
            x=x,
            y=y,
            width=w,
            height=h,
            frame_width=self.image.width,
            frame_height=self.image.height,
        )


def select_roi_from_video(video_path: Path, output_path: Path, reference_path: Path | None = None) -> ROI:
    if reference_path is None:
        reference_path = output_path.parent / "reference_frame.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    extract_reference_frame(video_path, reference_path)

    with Image.open(reference_path) as image:
        selector = ROISelector(image, source_name=video_path.name)
        roi = selector.run()

    if roi is None:
        raise RuntimeError("ROI selection was cancelled.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(roi.to_json() + "\n", encoding="utf-8")
    return roi


def load_roi(path: Path) -> ROI:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ROI(
        x=int(data["x"]),
        y=int(data["y"]),
        width=int(data["width"]),
        height=int(data["height"]),
        frame_width=int(data["frame_width"]),
        frame_height=int(data["frame_height"]),
    )
