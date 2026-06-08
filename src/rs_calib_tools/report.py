from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import yaml


def make_report(
    output_dir: str | Path = "outputs/calibration",
    qc_dir: str | Path = "outputs/qc",
) -> tuple[Path, Path]:
    calibration_dir = Path(output_dir)
    qc_path = Path(qc_dir)
    root = calibration_dir.parent.parent
    calibration_dir.mkdir(parents=True, exist_ok=True)

    factory_path = calibration_dir / "d435i_factory_intrinsics_extrinsics.json"
    charuco_path = calibration_dir / "d435i_color_opencv_charuco_intrinsics.json"
    summary_path = calibration_dir / "calibration_summary.json"
    html_path = calibration_dir / "calibration_report.html"

    factory = _read_json(factory_path)
    charuco = _read_json(charuco_path)
    pattern_files = _pattern_status(root / "assets" / "patterns")
    board_warnings = _board_config_warnings(root / "configs" / "boards")
    calibration_image_count = _count_calibration_images(root / "data" / "calibration_images" / "d435i_color_charuco")
    undistort_previews = sorted((qc_path / "color_undistort_preview").glob("undistort_*_compare.png"))
    overlays = sorted((qc_path / "rgbd_alignment_preview").glob("depth_overlay_*.png"))
    warnings: list[str] = []

    missing_patterns = [path for path, present in pattern_files.items() if not present]
    if missing_patterns:
        warnings.append("pattern_files_missing")
    if factory is None:
        warnings.append("factory_intrinsics_missing")
    if charuco is None:
        warnings.append("charuco_calibration_missing")
    if calibration_image_count < 10:
        warnings.append("calibration_images_count_below_10")
    if not undistort_previews:
        warnings.append("color_undistort_preview_missing")
    if not overlays:
        warnings.append("rgbd_alignment_preview_missing")
    warnings.extend(board_warnings)
    if charuco and charuco.get("warnings"):
        warnings.extend(str(value) for value in charuco["warnings"])

    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "pattern_files": pattern_files,
        "pattern_files_present": all(pattern_files.values()),
        "factory_intrinsics_present": factory is not None,
        "charuco_calibration_present": charuco is not None,
        "rms_reprojection_error_px": charuco.get("rms_reprojection_error_px") if charuco else None,
        "num_images_used": charuco.get("num_images_used") if charuco else 0,
        "num_images_rejected": charuco.get("num_images_rejected") if charuco else 0,
        "calibration_image_count": calibration_image_count,
        "color_undistort_preview_count": len(undistort_previews),
        "rgbd_alignment_preview_count": len(overlays),
        "warnings": sorted(set(warnings)),
        "next_steps": _next_steps(factory, charuco, calibration_image_count, overlays),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(summary), encoding="utf-8")
    return summary_path, html_path


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _pattern_status(pattern_dir: Path) -> dict[str, bool]:
    stems = [
        "charuco_A4_7x5_25mm",
        "checker_A4_9x6_20mm",
        "aruco_marker_sheet_A4",
    ]
    suffixes = [".svg", ".pdf", ".png"]
    return {f"{stem}{suffix}": (pattern_dir / f"{stem}{suffix}").exists() for stem in stems for suffix in suffixes}


def _board_config_warnings(board_dir: Path) -> list[str]:
    warnings: list[str] = []
    for path in sorted(board_dir.glob("*.yaml")):
        config = _read_yaml(path)
        if not config:
            continue
        board_id = config.get("board_id", path.stem)
        if config.get("square_size_mm_nominal") is not None and config.get("square_size_mm_measured") is None:
            warnings.append(f"{board_id}:square_size_mm_measured_missing")
        if config.get("marker_size_mm_nominal") is not None and config.get("marker_size_mm_measured") is None:
            warnings.append(f"{board_id}:marker_size_mm_measured_missing")
    return warnings


def _count_calibration_images(image_dir: Path) -> int:
    suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    if not image_dir.exists():
        return 0
    return sum(1 for path in image_dir.glob("*") if path.suffix.lower() in suffixes)


def _next_steps(factory: dict[str, Any] | None, charuco: dict[str, Any] | None, image_count: int, overlays: list[Path]) -> list[str]:
    steps = ["Print SVG or PDF targets at 100% actual size and measure physical square/marker sizes."]
    if factory is None:
        steps.append("Connect the D435i and export factory intrinsics/extrinsics/depth_scale.")
    if image_count < 30:
        steps.append("Capture 30-60 ChArUco color calibration images after mounting the printed board.")
    if charuco is None:
        steps.append("Run OpenCV ChArUco color-camera calibration and inspect RMS reprojection error.")
    if not overlays:
        steps.append("Capture RGB-D alignment overlays and inspect depth-to-color edge alignment visually.")
    return steps


def _render_html(summary: dict[str, Any]) -> str:
    rows = [
        ("Pattern files", "yes" if summary["pattern_files_present"] else "no"),
        ("Factory intrinsics", "yes" if summary["factory_intrinsics_present"] else "no"),
        ("ChArUco calibration", "yes" if summary["charuco_calibration_present"] else "no"),
        ("RMS error px", _fmt(summary["rms_reprojection_error_px"])),
        ("Calibration images", str(summary["calibration_image_count"])),
        ("Images used", str(summary["num_images_used"])),
        ("Images rejected", str(summary["num_images_rejected"])),
        ("Undistort previews", str(summary["color_undistort_preview_count"])),
        ("RGB-D previews", str(summary["rgbd_alignment_preview_count"])),
        ("Warnings", ", ".join(summary["warnings"]) or "none"),
        ("Next steps", " | ".join(summary["next_steps"])),
    ]
    table_rows = "\n".join(
        f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>" for key, value in rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>RealSense Calibration Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; line-height: 1.5; }}
    table {{ border-collapse: collapse; min-width: 520px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: left; }}
    th {{ background: #f2f2f2; }}
  </style>
</head>
<body>
  <h1>RealSense Calibration Report</h1>
  <table>
    {table_rows}
  </table>
</body>
</html>
"""


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
