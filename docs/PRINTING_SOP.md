# Printing and Mounting SOP

## Targets

- A4 ChArUco board: main board for RealSense color camera calibration and DSLR
  intrinsic calibration. Do not cut it.
- A4 checkerboard: backup traditional OpenCV calibration board. Do not cut it.
- A4 ArUco marker sheet: cuttable local reference markers for scale and pose
  context in a capture scene.

## Print Settings

1. Print SVG or PDF at actual size / 100%.
2. Disable "fit to page".
3. Disable "shrink oversized pages".
4. Do not crop the white border.
5. Use high-quality printing.
6. Matte paper is preferred.
7. Avoid glossy paper because reflections can break corner detection.

## Measurement After Printing

1. Measure `square_size_mm_measured` on the ChArUco and checkerboard targets.
2. Measure `marker_size_mm_measured` on the ChArUco target.
3. Measure the ArUco marker side length on the marker sheet.
4. Measure multiple positions across the page and record the average.
5. Write measured values back into `configs/boards/*.yaml` before calibration.

## Mounting

1. Mount the ChArUco and checkerboard sheets on a rigid flat board, such as foam
   board, acrylic board, or rigid cardboard.
2. Do not use wrinkled paper, soft paper, or a warped sheet as the main
   calibration target.
3. Do not split the main calibration board into pieces.
4. ArUco markers may be cut and placed near reference points in the scene, but
   each marker should stay fully visible and unobstructed.
5. Place ArUco markers as close as practical to the same plane as the measured
   surface.
6. Capture one record image showing the target board and a physical ruler.

## Capture Guidance

1. Capture 30-60 ChArUco color calibration images.
2. Cover the image center, corners, and edges.
3. Include front-facing, left/right tilted, and up/down tilted board poses.
4. Keep the board roughly 30%-70% of the image area.
5. Reject blurred, overexposed, strongly reflective, or partially hidden boards.

## Risk Notes

Printer scaling is the most common calibration failure source. A visually clean
board is not enough; the physical square and marker sizes must match the values
used by OpenCV.
