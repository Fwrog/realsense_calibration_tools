# Automatic calibration guide

## Prepare

- Connect over USB 3 and close other applications using the camera.
- Mount the complete ChArUco board on a flat, rigid surface; avoid glare and bending.
- Match the configuration: 5 × 7 squares, `DICT_5X5_100`, 17 markers and 24 inner corners.
- Measure the square side and outer black marker side, then update the YAML `*_measured` fields.
  The repository's 24 / 12 mm measurements apply to the demo print only.
- Generated targets have nominal sizes of 25 / 12.5 mm; printing can change physical dimensions.

## Inspect, then capture

`inspect` exports factory parameters, detects the board, estimates pose and produces a
single-view depth diagnostic. It does **not** refit intrinsics. `--confirm-board-size` confirms
that the physical print matches the measured YAML dimensions; otherwise metric pose is provisional.

`auto` filters blurry, moving and near-duplicate views, saves accepted images and fits color
intrinsics. Aim for 25 or more views, holding each pose for about two seconds:

1. Cover the center and image edges; keep the full board visible when possible.
2. Vary distance while keeping the small markers clearly resolvable.
3. Tilt around horizontal and vertical axes; front-facing translations alone are insufficient.

The software does not physically move the camera or board. A stationary setup normally saves
one view and finishes with `needs_more_views`, without intrinsic calibration. Every run uses a
separate directory. `capture.json` records corner counts, sharpness, normalized board vertices and time.

- `--preview`: show live detection; omit for headless operation.
- **Q / Esc**: stop capture and preserve accepted images.
- `--seconds`: time limit; `--views`: target count, at least 15.
- Exit code `2`: more views, a visible board or physical-size confirmation is needed.
- `calibration_candidate_needs_validation`: fitting completed, but accuracy is not certified.

About 20% of accepted views are excluded from the intrinsic fit. Their poses are then refitted
for held-out reprojection diagnostics. Capture thresholds are heuristics, not proof of adequate
geometric coverage or parameter observability.

## Interpret results

| Result | Interpretation |
|---|---|
| `T_color_from_board` | `p_color = R @ p_board + t`; translation in meters |
| `aligned_depth.npy` | SDK-aligned raw depth; multiply by factory depth scale for meters |
| Depth consistency | Median valid depth in a 5 × 5 corner neighborhood minus PnP-predicted Z |
| Training RMS | Pixel reprojection error on views used to fit intrinsics |
| Held-out mean RMS | Arithmetic mean of per-view RMS, with each held-out pose refitted |

Board coordinates follow OpenCV's ChArUco definition. Color-camera axes are x right, y down,
z forward. Pose estimation uses factory color intrinsics. Nonzero distortion is accepted only
for standard Brown–Conrady; inverse/modified coefficients are not silently treated as OpenCV
coefficients. Exactly zero coefficients are compatible with this calculation.

Depth consistency combines board-size, pose, alignment and depth errors. It is not independent
depth, alignment or length-accuracy validation. Missing depth has no valid statistic.
Held-out reprojection is likewise not independent metric ground truth.

Review residuals, view coverage and parameter plausibility, and compare with factory intrinsics
under the same conditions before adopting a candidate. New intrinsics apply only to the same
resolution and imaging configuration. `rs.align` still uses factory calibration; replacing color K
does not update SDK alignment or calibrate the depth module.

## Artifacts and privacy

Each `outputs/sessions/<timestamp>/` contains factory parameters, the board configuration,
inspection RGB/depth frames, selected images, capture records and a JSON/HTML report.
Successful fitting adds `color_intrinsics.json`, detection and undistortion previews.
No parameters are written to device firmware.

Raw sessions, serial numbers and machine-specific outputs remain local and Git-ignored.
The public demo includes an explicitly approved detection image and anonymized metrics.
Tests use synthetic boards.

On Windows, use an activated Conda environment or `conda run`. Calling an environment's
`python.exe` without activation can omit DLL search paths required by numerical libraries.

## References

- [OpenCV ChArUco calibration: multiple viewpoints](https://docs.opencv.org/4.5.0/da/d13/tutorial_aruco_calibration.html)
- [RealSense projection and distortion models](https://github.com/realsenseai/librealsense/wiki/Projection-in-RealSense-SDK-2.0)
