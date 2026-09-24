# RealSense Calibration Tools ✨

A marker-guided toolkit for RealSense D435i calibration workflows: live inspection,
automatic diverse-view capture, software color calibration, and local RGB-D diagnostics.

## 自动标定 · Quick start

**自动化的是检测、筛图、求解和报告；不同视角仍需人工移动相机或标定板。**
固定机位反复采集不等于完成内参标定。所有结果只写入本地，不修改相机固件。

After the environment setup below, run from this repository:

```powershell
# Inspect the connected device and board; save RGB, depth, pose and HTML report
conda run --no-capture-output -n rs_calib python scripts/run_calib.py --mode inspect --seconds 10

# Measure the printed board and update the measured dimensions in its YAML first.
# Move the camera/board; hold each different view still for about 2 seconds.
conda run --no-capture-output -n rs_calib python scripts/run_calib.py --mode auto --seconds 180 --views 25 --preview --confirm-board-size
```

Each run creates a new, non-overwriting `outputs/sessions/<timestamp>/` directory:

| Artifact | Meaning |
|---|---|
| `factory.json`, `board.yaml` | Device parameters and exact board configuration snapshot |
| `color.png`, `detection.png`, `aligned_depth.npy` | Best detected inspection frame and aligned raw depth |
| `images/`, `capture.json` | Accepted calibration views and quality/novelty measurements |
| `color_intrinsics.json` | Software calibration candidate, when enough views are collected |
| `summary.json`, `report.html` | Completion state, pose, diagnostics, limitations |

Automatic capture requires at least 12 detected corners, a sharp board region,
a stable pose, and a sufficiently different projected board footprint. These are
engineering heuristics, not a guarantee of calibration observability. Cover edges,
center, several distances and **out-of-plane tilts**, not just in-plane translation.
About 20% of accepted views are held out of the intrinsic fit; their poses are refitted
for a held-out reprojection diagnostic. A candidate is **not** automatically certified
as better than factory calibration. See [workflow and interpretation](docs/AUTOMATIC_CALIBRATION.md).

`rs-calib` is also available after `pip install -e .`; configuration paths are relative
to the working directory unless supplied explicitly. Exit code `2` means acquisition
or board confirmation is incomplete, not success. `--preview` opens an interactive window;
omit it for a headless run. `Q` stops acquisition and preserves accepted images.

The goal is simple: generate printable calibration targets, export RealSense factory parameters, calibrate the color camera with OpenCV ChArUco, inspect RGB-D depth-to-color alignment, and produce a compact calibration package.


## ✅ What It Does

- 🎯 Generates printable A4 targets:
  - ChArUco board: the main calibration board, not cuttable
  - Checkerboard: traditional OpenCV backup board, not cuttable
  - ArUco marker sheet: cuttable field reference markers
- 📷 Exports RealSense D435i factory intrinsics, extrinsics, and depth scale
- 🖼️ Captures RealSense color calibration images
- 🤖 Automatically selects sharp, stable, non-duplicate ChArUco views
- 📐 Estimates board-to-color pose using factory intrinsics and checks local depth consistency
- 🧮 Calibrates RealSense color camera intrinsics with OpenCV ChArUco
- ✨ Generates color-camera undistortion previews
- 🌈 Uses RealSense SDK `rs.align(rs.stream.color)` for RGB-D alignment QC previews
- 📦 Creates a calibration package and HTML report


Important boundary: OpenCV ChArUco calibration here estimates the software-level **color camera intrinsics**. It does not recalibrate the RealSense depth module.

## 🧰 Setup

Use a dedicated Conda environment. Avoid mixing this toolkit with YOLO, reconstruction, or other experiment environments.

```powershell
conda env create -f environment.yml
conda activate rs_calib
pip install -e .
```

If the environment already exists:

```powershell
conda env update -f environment.yml --prune
conda activate rs_calib
pip install -e .
```

Check the environment:

```powershell
conda run -n rs_calib python -c "import cv2, reportlab, pyrealsense2; print(cv2.__version__)"
```

`pyrealsense2` wheels are platform-specific. If installation fails, install the Intel RealSense SDK first, then retry the environment setup.

## 🚀 Typical Workflow

Run commands from the repository root.

### 1. Generate Printable Targets

```powershell
conda run -n rs_calib python scripts\01_generate_patterns.py
```

Outputs:

```text
assets/patterns/
```

Each target is generated as `.svg`, `.pdf`, and `.png`. SVG is the preferred print source, PDF is the convenient print fallback, and PNG is mainly for preview.

### 2. Print and Measure

Before calibration:

- ✅ Print at 100% Actual Size
- ❌ Do not use Fit to page
- ❌ Do not scale or shrink oversized pages
- ❌ Do not crop the white border
- ✅ Measure the printed square and marker sizes with a ruler or caliper
- ✅ Write measured values back into `configs/boards/*.yaml`

Do not cut the main ChArUco board or checkerboard. The ArUco marker sheet can be cut and placed near reference points in a scene, but each marker should stay fully visible and unobstructed.

See:

```text
docs/PRINTING_SOP.md
```

### 3. Export RealSense Factory Parameters

Requires a connected RealSense D435i.

```powershell
conda run -n rs_calib python scripts\02_export_realsense_intrinsics.py
```

Output:

```text
outputs/calibration/d435i_factory_intrinsics_extrinsics.json
```

`outputs/` is ignored by Git to avoid committing real device serial numbers or local calibration data.

### 4. Capture Color Calibration Images

Requires a printed and mounted ChArUco board.

```powershell
conda run -n rs_calib python scripts\03_capture_color_calib_images.py
```

- `SPACE` saves an image
- `ESC` / `q` exits
- Default output: `data/calibration_images/d435i_color_charuco/`

Recommended capture count: 30-60 images covering the image center, corners, and edges, with multiple board tilts.

### 5. Run OpenCV ChArUco Calibration

```powershell
conda run -n rs_calib python scripts\04_calibrate_color_charuco.py
```

Outputs:

```text
outputs/calibration/d435i_color_opencv_charuco_intrinsics.json
outputs/qc/charuco_detection_preview/
outputs/qc/color_undistort_preview/
```

If fewer than 10 valid images are detected, the script fails clearly instead of pretending calibration succeeded.

### 6. Check RGB-D Alignment

```powershell
conda run -n rs_calib python scripts\05_check_rgbd_alignment.py
```

- `SPACE` saves color, aligned depth, and overlay preview
- `ESC` / `q` exits
- The overlay is a visual QC preview. Inspect object edges manually for obvious depth-to-color misalignment.

### 7. Make Report

```powershell
conda run -n rs_calib python scripts\06_make_report.py
```

Outputs:

```text
outputs/calibration/calibration_summary.json
outputs/calibration/calibration_report.html
```

The report can still be generated before device capture; it will include warnings for missing calibration artifacts.

## 📦 Calibration Package

The final local calibration package is written to:

```text
outputs/calibration/
```

Typical files:

- `d435i_factory_intrinsics_extrinsics.json`
- `d435i_color_opencv_charuco_intrinsics.json`
- `calibration_summary.json`
- `calibration_report.html`

These files may contain machine-specific or device-specific data, so they are ignored by Git.

## 🗂️ Project Layout

```text
configs/      Board and camera YAML configs
assets/       Printable SVG/PDF/PNG patterns
scripts/      Six runnable workflow scripts
src/          Core Python package: rs_calib_tools
docs/         SOP and output schema notes
data/         Local captured images, ignored by Git
outputs/      Local calibration package and QC previews, ignored by Git
tests/        Synthetic detection, pose, data-integrity and report tests
```

## Testing and scope

```powershell
conda run -n rs_calib python -m unittest discover -s tests -v
```

GitHub Actions runs synthetic/software tests. It does not access a physical camera.
Real captures, serial numbers, local reports and measured calibration packages stay
Git-ignored. Share them only after an explicit privacy review.

Not implemented: depth-module/firmware self-calibration, multi-camera extrinsic
calibration, robot hand-eye calibration, or automatic mechanical board movement.
No neural detector is needed for this known ChArUco pattern.
