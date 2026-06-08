from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export D435i factory intrinsics, extrinsics, and depth scale.")
    parser.add_argument("--camera-config", default=ROOT / "configs" / "camera" / "d435i.yaml", type=Path)
    parser.add_argument(
        "--output",
        default=ROOT / "outputs" / "calibration" / "d435i_factory_intrinsics_extrinsics.json",
        type=Path,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from rs_calib_tools.realsense_device import export_intrinsics, load_camera_config

        output = export_intrinsics(args.output, load_camera_config(args.camera_config))
        print(f"Wrote {output}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

