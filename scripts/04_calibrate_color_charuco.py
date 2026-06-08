from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate RealSense color camera intrinsics using ChArUco images.")
    parser.add_argument(
        "--image-dir",
        default=ROOT / "data" / "calibration_images" / "d435i_color_charuco",
        type=Path,
    )
    parser.add_argument(
        "--board-config",
        default=ROOT / "configs" / "boards" / "charuco_A4_7x5_25mm.yaml",
        type=Path,
    )
    parser.add_argument(
        "--output",
        default=ROOT / "outputs" / "calibration" / "d435i_color_opencv_charuco_intrinsics.json",
        type=Path,
    )
    parser.add_argument(
        "--preview-dir",
        default=ROOT / "outputs" / "qc" / "charuco_detection_preview",
        type=Path,
    )
    parser.add_argument(
        "--undistort-preview-dir",
        default=ROOT / "outputs" / "qc" / "color_undistort_preview",
        type=Path,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from rs_calib_tools.calibration import calibrate_color_camera_charuco

        output = calibrate_color_camera_charuco(
            args.image_dir,
            args.board_config,
            args.output,
            args.preview_dir,
            args.undistort_preview_dir,
        )
        print(f"Wrote {output}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
