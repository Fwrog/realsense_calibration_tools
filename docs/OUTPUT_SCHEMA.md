# Session outputs

The main workflow writes only to `outputs/sessions/<timestamp>/`.
`summary.json` is the report's source of truth; `report.html` is its compact, human-readable view.
Rebuilding a report reads that session only and never accesses the camera or reruns calibration.

| Artifact | Contents |
|---|---|
| `factory.json` | Device identity, stream intrinsics, extrinsics and depth scale |
| `board.yaml` | Snapshot of the measured board configuration |
| `images/`, `capture.json` | Accepted images and quality/pose records |
| `color.png`, `detection.png`, `aligned_depth.npy` | Best inspection frame, detection overlay and aligned raw depth |
| `color_intrinsics.json` | Intrinsic fit, training image list and held-out errors |
| `summary.json`, `report.html` | Session state, metrics, diagnostics, warnings and next action |

## Summary fields

- `status`: inspection, incomplete, failed, interrupted, or calibration candidate; never implicit certification.
- `accepted_views`, `best_corner_count`, `physical_size_confirmed`: acquisition evidence.
- `intrinsics_recalibrated`, `firmware_modified`: distinguish software fitting from device changes.
- `calibration_metrics`: training RMS, held-out mean RMS, `num_images_used` (training views only),
  `heldout_views` (`path`, `rms_px`), and the validation scope. Absent before a successful fit.
- Optional measured comparison: `heldout_factory_mean_rms_px` and per-view `factory_rms_px`.
  The report displays these only when supplied; it does not invent or recompute a factory baseline.
- `board_pose`, `depth_consistency`: factory-based pose and single-view depth diagnostics.
- `warnings`, `error`: caveats and failure details, preserved in the compact report and JSON.

The HTML shows the detection image, key metrics, per-view error bars, caveats and next action.
Full details are collapsed by default. Missing metrics read **Not available**, not zero.
Each final capture record and report is written once, including on recoverable Python exceptions.

## Rebuild a report

```bash
python scripts/run_calib.py --mode report --session outputs/sessions/SESSION
```

`python scripts/06_make_report.py --session outputs/sessions/SESSION` calls the same renderer.
The former `--output-dir` / `--qc-dir` report interface is replaced by `--session`.
Existing legacy files are not deleted or automatically merged into a session.

These outputs can contain device serial numbers, local paths and scene images. Keep them local
unless explicitly reviewed for publication. Public demo results are a separate, anonymized export.
