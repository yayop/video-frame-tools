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

## Windows setup

The tool works on Windows from PowerShell. The most reliable workflow is to use a Python virtual environment and run the package with `python -m video_frame_tools`.

### 1. Install Python and Git

Install Python 3.9 or newer from https://www.python.org/downloads/windows/ and enable `Add python.exe to PATH` during installation.

You can also install Python and Git from PowerShell with `winget`:

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
```

Close and reopen PowerShell after installing command-line tools, then verify:

```powershell
python --version
git --version
```

### 2. Get the project

```powershell
git clone https://github.com/yayop/video-frame-tools.git
cd video-frame-tools
```

If you downloaded the ZIP from GitHub instead, extract it and open PowerShell inside the extracted folder.

### 3. Create a virtual environment

Make sure PowerShell is inside the cloned project folder before creating or using the virtual environment:

```powershell
pwd
Test-Path pyproject.toml
```

`Test-Path pyproject.toml` should print `True`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If PowerShell blocks activation scripts, run this once and then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 4. FFmpeg on Windows

You do not strictly need to install a system `ffmpeg`. This project depends on `imageio-ffmpeg`, which provides a bundled `ffmpeg` binary and is installed by `python -m pip install -e .`.

If you want a system `ffmpeg` available from PowerShell, install it with `winget`:

```powershell
winget install -e --id Gyan.FFmpeg
```

Then close and reopen PowerShell and verify:

```powershell
ffmpeg -version
```

If you already use Chocolatey, this is another option:

```powershell
choco install ffmpeg -y
```

Manual downloads are available from the official FFmpeg download page: https://www.ffmpeg.org/download.html

### 5. Run ROI selection on Windows

Use a full video path or run the command from the folder containing the video:

```powershell
python -m video_frame_tools roi "C:\Users\YourName\Videos\input.mp4"
```

The ROI selector opens in your default browser. Draw a rectangle and click `Save ROI`.

For `C:\Users\YourName\Videos\input.mp4`, the tool creates:

```text
C:\Users\YourName\Videos\input\
  roi.json
  reference_frame.png
  video_metadata.txt
```

### 6. Extract grayscale first

```powershell
python -m video_frame_tools extract "C:\Users\YourName\Videos\input.mp4" --roi "C:\Users\YourName\Videos\input\roi.json" --channels gray --workers 4
```

### 7. Extract the remaining channels

```powershell
python -m video_frame_tools extract "C:\Users\YourName\Videos\input.mp4" --roi "C:\Users\YourName\Videos\input\roi.json" --channels green red blue --workers 4
```

The final output folder will contain `gray`, `green`, `red`, and `blue` subfolders, plus `manifest.json` and `video_metadata.txt`.

### Windows troubleshooting

If you see `No module named video_frame_tools`, PowerShell is usually in the wrong folder or the package was not installed in the active virtual environment.

Check your current folder:

```powershell
pwd
Test-Path pyproject.toml
```

If `Test-Path pyproject.toml` prints `False`, go to the cloned repository folder:

```powershell
cd "$env:USERPROFILE\video-frame-tools"
```

If your clone is somewhere else, use that path instead.

Then activate the environment and install the project again:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m video_frame_tools --help
```

If PowerShell is currently in `C:\WINDOWS\system32`, do not create the project or virtual environment there. Move to a user folder such as `Documents`, `Desktop`, or your Git clone folder first.

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
