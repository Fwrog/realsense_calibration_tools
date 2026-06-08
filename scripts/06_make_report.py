from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate calibration summary JSON and HTML report.")
    parser.add_argument("--output-dir", default=ROOT / "outputs" / "calibration", type=Path)
    parser.add_argument("--qc-dir", default=ROOT / "outputs" / "qc", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from rs_calib_tools.report import make_report

        summary_path, html_path = make_report(args.output_dir, args.qc_dir)
        print(f"Wrote {summary_path}")
        print(f"Wrote {html_path}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

