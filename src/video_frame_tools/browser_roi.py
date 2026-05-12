from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PIL import Image

from .ffmpeg_utils import extract_reference_frame
from .roi_selector import ROI


def _html() -> bytes:
    return b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ROI selector</title>
  <style>
    :root {
      color-scheme: light;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f2;
      color: #191917;
    }
    body { margin: 0; }
    .bar {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      border-bottom: 1px solid #d8d6ce;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    button {
      border: 1px solid #1f1f1c;
      background: #1f1f1c;
      color: #fff;
      padding: 7px 12px;
      border-radius: 6px;
      cursor: pointer;
    }
    button.secondary { background: #fff; color: #1f1f1c; }
    #coords { min-width: 260px; font-variant-numeric: tabular-nums; }
    .stage {
      height: calc(100vh - 52px);
      display: grid;
      place-items: center;
      overflow: auto;
      padding: 12px;
      box-sizing: border-box;
    }
    canvas {
      max-width: 100%;
      max-height: calc(100vh - 80px);
      border: 1px solid #20201c;
      background: #111;
      cursor: crosshair;
    }
  </style>
</head>
<body>
  <div class="bar">
    <button id="save">Save ROI</button>
    <button class="secondary" id="reset">Reset</button>
    <button class="secondary" id="cancel">Cancel</button>
    <span id="coords">x=0 y=0 w=0 h=0</span>
  </div>
  <div class="stage">
    <canvas id="canvas"></canvas>
  </div>
  <script>
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const coords = document.getElementById("coords");
    const image = new Image();
    let start = null;
    let selection = null;

    image.onload = () => {
      const maxW = Math.min(window.innerWidth - 24, image.naturalWidth);
      const maxH = Math.min(window.innerHeight - 86, image.naturalHeight);
      const scale = Math.min(maxW / image.naturalWidth, maxH / image.naturalHeight, 1);
      canvas.width = Math.round(image.naturalWidth * scale);
      canvas.height = Math.round(image.naturalHeight * scale);
      draw();
    };
    image.src = "/reference_frame.png";

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      if (!selection) return;
      ctx.strokeStyle = "#00d1ff";
      ctx.lineWidth = 2;
      ctx.strokeRect(selection.x, selection.y, selection.w, selection.h);
      ctx.fillStyle = "rgba(0, 209, 255, 0.15)";
      ctx.fillRect(selection.x, selection.y, selection.w, selection.h);
    }

    function toCanvasPoint(event) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(canvas.width, event.clientX - rect.left)),
        y: Math.max(0, Math.min(canvas.height, event.clientY - rect.top)),
      };
    }

    function toImageROI(sel) {
      const scaleX = image.naturalWidth / canvas.width;
      const scaleY = image.naturalHeight / canvas.height;
      const x = Math.round(sel.x * scaleX);
      const y = Math.round(sel.y * scaleY);
      const width = Math.max(1, Math.round(sel.w * scaleX));
      const height = Math.max(1, Math.round(sel.h * scaleY));
      return { x, y, width, height, frame_width: image.naturalWidth, frame_height: image.naturalHeight };
    }

    function updateCoords() {
      if (!selection) {
        coords.textContent = "x=0 y=0 w=0 h=0";
        return;
      }
      const roi = toImageROI(selection);
      coords.textContent = `x=${roi.x} y=${roi.y} w=${roi.width} h=${roi.height}`;
    }

    canvas.addEventListener("mousedown", (event) => {
      start = toCanvasPoint(event);
      selection = { x: start.x, y: start.y, w: 1, h: 1 };
      draw();
      updateCoords();
    });

    canvas.addEventListener("mousemove", (event) => {
      if (!start) return;
      const point = toCanvasPoint(event);
      selection = {
        x: Math.min(start.x, point.x),
        y: Math.min(start.y, point.y),
        w: Math.max(1, Math.abs(point.x - start.x)),
        h: Math.max(1, Math.abs(point.y - start.y)),
      };
      draw();
      updateCoords();
    });

    window.addEventListener("mouseup", () => { start = null; });

    document.getElementById("reset").addEventListener("click", () => {
      selection = null;
      draw();
      updateCoords();
    });

    document.getElementById("cancel").addEventListener("click", async () => {
      await fetch("/cancel", { method: "POST" });
      document.body.innerHTML = "<p style='font: 16px sans-serif; padding: 24px'>ROI selection cancelled. You can close this tab.</p>";
    });

    document.getElementById("save").addEventListener("click", async () => {
      if (!selection) {
        alert("Draw a rectangle first.");
        return;
      }
      const roi = toImageROI(selection);
      const response = await fetch("/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(roi),
      });
      if (!response.ok) {
        alert("Could not save ROI.");
        return;
      }
      document.body.innerHTML = "<p style='font: 16px sans-serif; padding: 24px'>ROI saved. You can close this tab.</p>";
    });
  </script>
</body>
</html>
"""


class _State:
    def __init__(self, reference_path: Path, output_path: Path) -> None:
        self.reference_path = reference_path
        self.output_path = output_path
        self.done = threading.Event()
        self.roi: ROI | None = None
        self.error: str | None = None


def _make_handler(state: _State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/":
                self._send_bytes(_html(), "text/html; charset=utf-8")
                return
            if self.path == "/reference_frame.png":
                self._send_bytes(state.reference_path.read_bytes(), "image/png")
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path == "/cancel":
                state.error = "ROI selection was cancelled."
                state.done.set()
                self._send_json({"ok": True})
                return
            if self.path != "/save":
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            roi = ROI(
                x=int(data["x"]),
                y=int(data["y"]),
                width=int(data["width"]),
                height=int(data["height"]),
                frame_width=int(data["frame_width"]),
                frame_height=int(data["frame_height"]),
            )
            state.output_path.parent.mkdir(parents=True, exist_ok=True)
            state.output_path.write_text(roi.to_json() + "\n", encoding="utf-8")
            state.roi = roi
            state.done.set()
            self._send_json({"ok": True})

        def _send_bytes(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, data: dict[str, object]) -> None:
            self._send_bytes(json.dumps(data).encode("utf-8"), "application/json")

    return Handler


def select_roi_in_browser(video_path: Path, output_path: Path, reference_path: Path) -> ROI:
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    extract_reference_frame(video_path, reference_path)

    with Image.open(reference_path) as image:
        image.verify()

    state = _State(reference_path=reference_path, output_path=output_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Opening browser ROI selector: {url}")
    webbrowser.open(url)

    state.done.wait()
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)

    if state.error:
        raise RuntimeError(state.error)
    if state.roi is None:
        raise RuntimeError("ROI selection did not produce a result.")
    return state.roi
