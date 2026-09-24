# RealSense workflow

Use `scripts/run_calib.py` as the main entry point:

1. **Inspect:** `--mode inspect` checks the connected camera and board.
2. **Capture and fit:** `--mode auto --preview --confirm-board-size` selects views and fits intrinsics.
3. **Review:** open the session's `report.html`; no separate report command is required.
4. **Rebuild if needed:** `--mode report --session outputs/sessions/SESSION` uses saved results only.

See the [automatic guide](AUTOMATIC_CALIBRATION.md) for board preparation, controls and interpretation,
and the [session schema](OUTPUT_SCHEMA.md) for artifacts.

## Optional manual tools

Numbered scripts remain available for focused inspection; they are not a second recommended pipeline.

| Script | Purpose |
|---|---|
| `01_generate_patterns.py` | Generate printable targets |
| `02_export_realsense_intrinsics.py` | Export factory parameters |
| `03_capture_color_calib_images.py` | Capture images manually |
| `04_calibrate_color_charuco.py` | Fit from saved images, optionally with `--holdout-count` |
| `05_check_rgbd_alignment.py` | Inspect SDK-aligned RGB-D overlays |
| `06_make_report.py` | Alias for the shared session-report renderer; requires `--session` |

Scripts 01–05 retain their existing defaults for standalone use. Their outputs are not automatically
merged into the main session report. Existing datasets and previous calibration packages remain untouched.

The toolkit estimates software color intrinsics and provides alignment diagnostics.
It does not recalibrate depth firmware or certify measurement accuracy.
