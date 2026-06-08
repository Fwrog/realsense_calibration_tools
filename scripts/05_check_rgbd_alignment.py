from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture aligned RGB-D preview frames for QC.")
    parser.add_argument("--camera-config", default=ROOT / "configs" / "camera" / "d435i.yaml", type=Path)
    parser.add_argument(
        "--output-dir",
        default=ROOT / "outputs" / "qc" / "rgbd_alignment_preview",
        type=Path,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from rs_calib_tools.realsense_device import capture_aligned_rgbd_preview, load_camera_config

        capture_aligned_rgbd_preview(args.output_dir, load_camera_config(args.camera_config))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

