# Tests

This directory is reserved for lightweight smoke tests.

Current public workflow validation is manual and command-based:

```powershell
conda run -n rs_calib python scripts\01_generate_patterns.py --help
conda run -n rs_calib python scripts\06_make_report.py --help
```

Do not place captured RealSense images, device-specific JSON, or large outputs
in this directory.
