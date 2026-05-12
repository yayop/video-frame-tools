from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video_frame_tools.cli import _default_output_dir, _default_report_path, _default_roi_path
from video_frame_tools.image_ops import channel_image, normalize_channels, save_channel_exports
from video_frame_tools.video_metadata import VideoMetadata


class ImageOpsTests(unittest.TestCase):
    def test_normalize_channels_all(self) -> None:
        self.assertEqual(normalize_channels(["all"]), ["red", "green", "blue", "gray"])

    def test_channel_image_uses_expected_channel_values(self) -> None:
        image = Image.new("RGB", (2, 1))
        image.putdata([(10, 20, 30), (40, 50, 60)])

        red = channel_image(image, "red")
        green = channel_image(image, "green")
        blue = channel_image(image, "blue")

        self.assertEqual(red.mode, "L")
        self.assertEqual(red.getpixel((0, 0)), 10)
        self.assertEqual(red.getpixel((1, 0)), 40)
        self.assertEqual(green.getpixel((0, 0)), 20)
        self.assertEqual(green.getpixel((1, 0)), 50)
        self.assertEqual(blue.getpixel((0, 0)), 30)
        self.assertEqual(blue.getpixel((1, 0)), 60)

    def test_save_channel_exports_writes_pngs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            source = tmpdir_path / "frame_000001.png"
            image = Image.new("RGB", (1, 1), (1, 2, 3))
            image.save(source)

            saved = save_channel_exports(source, tmpdir_path / "out", ["red", "gray"])

            self.assertIn("red", saved)
            self.assertIn("gray", saved)
            self.assertTrue(saved["red"].exists())
            self.assertTrue(saved["gray"].exists())

    def test_default_paths_are_sibling_outputs(self) -> None:
        video = Path("/Users/edgardo/Desktop/Research Projects/Video transformer/20260511_165928A.mp4")
        self.assertEqual(
            _default_output_dir(video),
            Path("/Users/edgardo/Desktop/Research Projects/Video transformer/20260511_165928A"),
        )
        self.assertEqual(
            _default_roi_path(video),
            Path("/Users/edgardo/Desktop/Research Projects/Video transformer/20260511_165928A/roi.json"),
        )
        self.assertEqual(
            _default_report_path(video),
            Path("/Users/edgardo/Desktop/Research Projects/Video transformer/20260511_165928A/video_metadata.txt"),
        )

    def test_video_metadata_text_includes_summary(self) -> None:
        metadata = VideoMetadata(
            input_video=Path("input.mp4"),
            created_at="2026-05-12T00:00:00+00:00",
            file_size_bytes=123,
            duration="00:00:01.00",
            duration_seconds=1.0,
            width=1920,
            height=1080,
            fps=30.0,
            estimated_total_frames=30,
            video_codec="h264",
            video_bitrate="1000 kb/s",
            audio_codec="aac",
            audio_info="mono",
            ffmpeg_executable="/usr/bin/ffmpeg",
        )
        text = metadata.to_text(extra={"frames_written": 10, "channels": ["red", "gray"]})
        self.assertIn("Video Metadata", text)
        self.assertIn("Run Summary", text)
        self.assertIn("frames_written: 10", text)
        self.assertIn('channels: ["red", "gray"]', text)


if __name__ == "__main__":
    unittest.main()
