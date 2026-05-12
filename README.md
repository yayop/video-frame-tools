# Video Frame Tools

Small, documented utility for turning a compressed video into a PNG frame sequence with optional ROI cropping and channel exports.

## What it does

- Extracts video frames as PNGs with `ffmpeg`
- Lets you select a crop ROI in the browser
- Supports quick left/right trimming without opening the GUI
- Exports four grayscale variants per frame:
  - `red`
  - `green`
  - `blue`
  - `gray`

This is a good fit when the color image itself is not important and you want channel-wise inputs for later processing.

## Requirements

- Python 3.9+
- `ffmpeg` available on your `PATH`, or the bundled fallback from `imageio-ffmpeg`

Install `ffmpeg` if you do not already have it:

- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Windows: install from https://ffmpeg.org/ and add it to `PATH`

If you prefer not to install a system `ffmpeg`, `pip install -e .` will also bring in `imageio-ffmpeg` and the tool will use that binary automatically.

## Install

```bash
pip install -e .
```

## Usage

### 1. Pick an ROI interactively

This opens the first frame in a local browser rectangle selector and saves the crop as JSON.

```bash
video-frames roi input.mp4 --output roi.json
```

If you omit `--output`, the tool creates the sibling folder `input/` if needed and writes `input/roi.json` there.
It also writes `input/video_metadata.txt` with video details and the selected ROI.
The first video frame is also saved as `input/reference_frame.png`, which is useful if the ROI window opens behind another app.
The legacy Tk selector is still available with `video-frames roi input.mp4 --tk`.

### 2. Extract frames with crop + channel exports

By default, the extractor writes PNGs into a sibling folder with the same name as the video stem.

```bash
video-frames extract input.mp4 --roi roi.json
```

Output structure:

```text
input/
  red/
    frame_000001.png
  green/
    frame_000001.png
  blue/
    frame_000001.png
  gray/
    frame_000001.png
  manifest.json
  video_metadata.txt
```

If your input is `/Users/edgardo/Desktop/Research Projects/Video transformer/20260511_165928A.mp4`,
the default output folder becomes:

```text
/Users/edgardo/Desktop/Research Projects/Video transformer/20260511_165928A/
```

### 3. Trim the sides directly from the CLI

If you want to cut equally on the left and right without using the GUI:

```bash
video-frames extract input.mp4 --trim-sides 40
```

Optional top and bottom trimming are also available:

```bash
video-frames extract input.mp4 --trim-sides 40 --trim-top 12 --trim-bottom 12
```

### 4. Extract only some channels

```bash
video-frames extract input.mp4 --output-dir output --channels red gray
```

### 5. Benchmark a sample

Use `--max-frames` to time a fixed slice of a video, and `--workers` to compare sequential versus parallel export:

```bash
video-frames extract input.mp4 --max-frames 200 --channels red green blue gray --workers 1
video-frames extract input.mp4 --max-frames 200 --channels red green blue gray --workers 4
```

## ROI workflow

The ROI selector is deliberately simple:

- it opens a representative frame
- you drag a rectangle
- it stores pixel coordinates in JSON

That makes it easy to reuse the same crop on other videos, or to share it with other humans.
The extractor validates the ROI against the video resolution before applying it.

By default, both the ROI JSON and the extracted channel folders live under the sibling folder named after the video stem.
Each run also leaves a `video_metadata.txt` report with video details and a short run summary.
The report includes an estimated total frame count, frame size, FPS, duration, and the exact number of frames written by the run.

## Notes

- The tool uses `ffmpeg` for decoding the compressed video.
- The channel exports are saved as grayscale PNGs. Each output image contains the intensity of a single channel.
- If you want a non-interactive batch workflow, the JSON ROI file is the recommended path.

## Development

Run the tests:

```bash
python -m unittest
```
