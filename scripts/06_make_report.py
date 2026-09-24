"""Manual alias for the shared session-report renderer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rs_calib_tools.report import main

if __name__ == "__main__":
    raise SystemExit(main())
