# Tests

Synthetic/software tests; no camera is required.

Run after installing the package:

```powershell
conda run -n rs_calib python -m unittest discover -s tests -v
```

Do not place captured RealSense images, device-specific JSON, or large outputs
in this directory.
