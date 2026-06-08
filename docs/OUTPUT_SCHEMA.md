# Output Schema

## d435i_factory_intrinsics_extrinsics.json

- `device`: RealSense device name, serial number, firmware version, product
  line, and SDK version when available.
- `streams.color`: color stream width, height, fps, format, and intrinsics.
- `streams.depth`: depth stream width, height, fps, format, intrinsics, and
  depth scale.
- `extrinsics.depth_to_color`: rotation matrix and translation vector from
  depth to color.
- `extrinsics.color_to_depth`: rotation matrix and translation vector from
  color to depth.

## d435i_color_opencv_charuco_intrinsics.json

- `method`: `opencv_charuco`.
- `square_length_m`: square length used by OpenCV, in metres.
- `marker_length_m`: marker length used by OpenCV, in metres.
- `K`: 3x3 OpenCV camera matrix for the color camera.
- `distortion`: OpenCV distortion coefficients.
- `rms_reprojection_error_px`: ChArUco calibration RMS reprojection error.
- `image_size`: `[width, height]`.
- `num_images_used`: number of accepted calibration images.
- `num_images_rejected`: number of rejected images.
- `used_images`: accepted image paths.
- `rejected_images`: rejected image paths with reasons.
- `warnings`: calibration warnings such as use of nominal board sizes.

## calibration_summary.json

Compact package status for downstream RGB-D projects:

- pattern SVG/PDF/PNG presence;
- factory metadata present or missing;
- OpenCV ChArUco calibration present or missing;
- RMS reprojection error when available;
- used and rejected image counts;
- color undistortion preview count;
- RGB-D alignment preview count;
- warnings.

## QC previews

- `outputs/qc/charuco_detection_preview/`: accepted ChArUco detection overlays.
- `outputs/qc/color_undistort_preview/`: before/after/compare previews for
  OpenCV color-camera lens undistortion.
- `outputs/qc/rgbd_alignment_preview/`: RealSense SDK depth-to-color alignment
  QC previews and raw aligned depth arrays.
