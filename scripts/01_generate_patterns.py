from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate printable A4 calibration patterns.")
    parser.add_argument("--output-dir", default=ROOT / "assets" / "patterns", type=Path)
    parser.add_argument(
        "--boards-dir",
        default=ROOT / "configs" / "boards",
        type=Path,
        help="Directory containing board YAML configs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from rs_calib_tools.patterns import generate_all_patterns

        board_configs = [
            args.boards_dir / "charuco_A4_7x5_25mm.yaml",
            args.boards_dir / "checker_A4_9x6_20mm.yaml",
            args.boards_dir / "aruco_marker_sheet_A4.yaml",
        ]
        generate_all_patterns(board_configs, args.output_dir)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

