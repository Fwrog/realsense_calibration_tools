# RealSense SOP

## Device Check

1. Open RealSense Viewer and confirm the D435i streams normally.
2. Check that color and depth streams can run together.
3. Let the device warm up before collecting calibration images.
4. Use RealSense Viewer health check or official self-calibration tools only as
   device-maintenance checks. They are not replaced by this toolkit.

## Calibration Flow

1. Export factory intrinsics, extrinsics, and depth scale.
2. Capture 30-60 ChArUco color images from varied board poses.
3. Run OpenCV ChArUco color-camera calibration.
4. Inspect color undistortion before/after previews.
5. Capture aligned RGB-D preview frames using `rs.align(rs.stream.color)`.
6. Inspect overlay previews for obvious depth-to-color mismatch.
7. Generate the calibration report.

## Boundary

This toolkit estimates software-layer color-camera intrinsics and validates SDK
depth-to-color alignment. It does not recalibrate RealSense depth-module
firmware.
