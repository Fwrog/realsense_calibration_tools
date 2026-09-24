from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml


def load_board_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def create_charuco_board(config: dict[str, Any]):
    aruco = cv2.aruco
    dictionary = _aruco_dictionary(config["dictionary"])
    square_size_mm = _measured_or_nominal(config, "square_size_mm")
    marker_size_mm = _measured_or_nominal(config, "marker_size_mm")
    square_m = square_size_mm / 1000.0
    marker_m = marker_size_mm / 1000.0
    squares_x = int(config["squares_x"])
    squares_y = int(config["squares_y"])
    if not (np.isfinite(square_m) and np.isfinite(marker_m) and 0 < marker_m < square_m):
        raise ValueError("Board sizes must be finite and satisfy 0 < marker < square.")
    if squares_x < 3 or squares_y < 3:
        raise ValueError("ChArUco board must have at least 3 x 3 squares.")

    if hasattr(aruco, "CharucoBoard"):
        try:
            return aruco.CharucoBoard((squares_x, squares_y), square_m, marker_m, dictionary)
        except TypeError:
            pass
    if hasattr(aruco, "CharucoBoard_create"):
        return aruco.CharucoBoard_create(squares_x, squares_y, square_m, marker_m, dictionary)
    raise RuntimeError("OpenCV aruco module does not provide ChArUco board support.")


def calibrate_color_camera_charuco(
    image_dir: str | Path,
    board_config_path: str | Path,
    output_json: str | Path,
    preview_dir: str | Path,
    undistort_preview_dir: str | Path | None = None,
    holdout_count: int = 0,
) -> Path:
    image_path = Path(image_dir)
    config = load_board_config(board_config_path)
    board = create_charuco_board(config)
    dictionary = _aruco_dictionary(config["dictionary"])
    output = Path(output_json)
    previews = Path(preview_dir)
    undistort_previews = Path(undistort_preview_dir) if undistort_preview_dir is not None else None
    previews.mkdir(parents=True, exist_ok=True)
    if undistort_previews is not None:
        undistort_previews.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    if config.get("square_size_mm_measured") is None:
        warnings.append("square_size_mm_measured missing; using nominal square size")
    if config.get("marker_size_mm_measured") is None:
        warnings.append("marker_size_mm_measured missing; using nominal marker size")

    all_corners = []
    all_ids = []
    used_images: list[str] = []
    rejected_images: list[dict[str, str]] = []
    image_size: tuple[int, int] | None = None
    square_length_m = _measured_or_nominal(config, "square_size_mm") / 1000.0
    marker_length_m = _measured_or_nominal(config, "marker_size_mm") / 1000.0

    images = sorted(
        path for path in image_path.glob("*")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    )
    if not images:
        raise RuntimeError(f"No calibration images found in {image_path}")

    for path in images:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            rejected_images.append({"path": str(path), "reason": "failed_to_read"})
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        current_size = (gray.shape[1], gray.shape[0])
        if image_size is not None and image_size != current_size:
            raise ValueError(f"Mixed image resolutions: {path} is {current_size}, expected {image_size}.")
        image_size = current_size

        marker_corners, marker_ids = _detect_markers(gray, dictionary)
        if marker_ids is None or len(marker_ids) == 0:
            rejected_images.append({"path": str(path), "reason": "no_aruco_markers"})
            continue

        retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners,
            marker_ids,
            gray,
            board,
        )
        if charuco_ids is None or charuco_corners is None or int(retval) < 6:
            rejected_images.append({"path": str(path), "reason": "too_few_charuco_corners"})
            continue
        if board.checkCharucoCornersCollinear(charuco_ids):
            rejected_images.append({"path": str(path), "reason": "collinear_corners"})
            continue

        all_corners.append(charuco_corners)
        all_ids.append(charuco_ids)
        used_images.append(str(path))
        preview = image.copy()
        cv2.aruco.drawDetectedMarkers(preview, marker_corners, marker_ids)
        cv2.aruco.drawDetectedCornersCharuco(preview, charuco_corners, charuco_ids)
        cv2.imwrite(str(previews / f"{path.stem}_charuco.png"), preview)

    if len(used_images) < 10:
        raise RuntimeError(
            f"Need at least 10 valid ChArUco images, got {len(used_images)}. "
            "Capture more board poses before calibration."
        )
    if image_size is None:
        raise RuntimeError("No readable calibration image size was found.")

    if holdout_count < 0 or len(used_images) - holdout_count < 10:
        raise ValueError("Holdout split must leave at least 10 training images.")
    held_indices = set(np.linspace(0, len(used_images)-1, holdout_count, dtype=int).tolist())
    train_indices = [i for i in range(len(used_images)) if i not in held_indices]

    rms, camera_matrix, dist_coeffs, _, _ = cv2.aruco.calibrateCameraCharuco(
        [all_corners[i] for i in train_indices],
        [all_ids[i] for i in train_indices],
        board,
        image_size,
        None,
        None,
    )
    if not np.isfinite(rms) or not np.isfinite(camera_matrix).all() or not np.isfinite(dist_coeffs).all() or min(camera_matrix[0, 0], camera_matrix[1, 1]) <= 0:
        raise RuntimeError("Calibration returned invalid numerical parameters.")
    heldout = []
    for i in sorted(held_indices):
        objects = board.getChessboardCorners()[all_ids[i].flatten()]
        ok, rvec, tvec = cv2.solvePnP(objects, all_corners[i], camera_matrix, dist_coeffs)
        if not ok:
            raise RuntimeError(f"Held-out pose estimation failed: {used_images[i]}")
        projected, _ = cv2.projectPoints(objects, rvec, tvec, camera_matrix, dist_coeffs)
        error = np.sqrt(np.mean(np.sum((projected.reshape(-1, 2)-all_corners[i].reshape(-1, 2))**2, axis=1)))
        if not np.isfinite(error):
            raise RuntimeError("Nonfinite held-out reprojection error.")
        heldout.append({"path": used_images[i], "rms_px": float(error)})
    if undistort_previews is not None:
        _write_undistort_previews(used_images, camera_matrix, dist_coeffs, undistort_previews)

    payload = {
        "schema_version": "1.0",
        "method": "opencv_charuco",
        "board_config": str(board_config_path),
        "board_id": config["board_id"],
        "square_length_m": square_length_m,
        "marker_length_m": marker_length_m,
        "K": np.asarray(camera_matrix).tolist(),
        "distortion": np.asarray(dist_coeffs).reshape(-1).tolist(),
        "rms_reprojection_error_px": float(rms),
        "image_size": [int(image_size[0]), int(image_size[1])],
        "num_images_used": len(train_indices),
        "num_images_detected": len(used_images),
        "heldout_views": heldout,
        "heldout_mean_rms_px": float(np.mean([v["rms_px"] for v in heldout])) if heldout else None,
        "validation_scope": "Held-out intrinsics reprojection diagnostic; pose refitted per view. Not metric ground truth or depth calibration.",
        "num_images_rejected": len(rejected_images),
        "used_images": [used_images[i] for i in train_indices],
        "rejected_images": rejected_images,
        "warnings": warnings,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"RMS reprojection error: {float(rms):.4f} px")
    print(f"Images train/held-out/rejected: {len(train_indices)}/{len(heldout)}/{len(rejected_images)}")
    if undistort_previews is not None:
        print(f"Undistortion previews: {undistort_previews}")
    return output


def _detect_markers(gray: np.ndarray, dictionary: Any):
    aruco = cv2.aruco
    parameters = aruco.DetectorParameters() if hasattr(aruco, "DetectorParameters") else aruco.DetectorParameters_create()
    if hasattr(aruco, "ArucoDetector"):
        detector = aruco.ArucoDetector(dictionary, parameters)
        corners, ids, _ = detector.detectMarkers(gray)
    else:
        corners, ids, _ = aruco.detectMarkers(gray, dictionary, parameters=parameters)
    return corners, ids


def _aruco_dictionary(name: str):
    aruco = cv2.aruco
    if not hasattr(aruco, name):
        raise RuntimeError(f"Unknown OpenCV ArUco dictionary: {name}")
    dictionary_id = getattr(aruco, name)
    if hasattr(aruco, "getPredefinedDictionary"):
        return aruco.getPredefinedDictionary(dictionary_id)
    return aruco.Dictionary_get(dictionary_id)


def _measured_or_nominal(config: dict[str, Any], prefix: str) -> float:
    measured = config.get(f"{prefix}_measured")
    if measured is not None:
        return float(measured)
    return float(config[f"{prefix}_nominal"])


def _write_undistort_previews(
    used_images: list[str],
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    output_dir: Path,
    max_images: int = 5,
) -> None:
    for index, image_path in enumerate(used_images[:max_images]):
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            continue
        undistorted = cv2.undistort(image, camera_matrix, dist_coeffs)
        compare = np.hstack([image, undistorted])
        cv2.imwrite(str(output_dir / f"undistort_{index:04d}_before.png"), image)
        cv2.imwrite(str(output_dir / f"undistort_{index:04d}_after.png"), undistorted)
        cv2.imwrite(str(output_dir / f"undistort_{index:04d}_compare.png"), compare)
