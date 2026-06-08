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
        image_size = (gray.shape[1], gray.shape[0])

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
        if charuco_ids is None or charuco_corners is None or int(retval) < 4:
            rejected_images.append({"path": str(path), "reason": "too_few_charuco_corners"})
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

    rms, camera_matrix, dist_coeffs, _, _ = cv2.aruco.calibrateCameraCharuco(
        all_corners,
        all_ids,
        board,
        image_size,
        None,
        None,
    )
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
        "num_images_used": len(used_images),
        "num_images_rejected": len(rejected_images),
        "used_images": used_images,
        "rejected_images": rejected_images,
        "warnings": warnings,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"RMS reprojection error: {float(rms):.4f} px")
    print(f"Images used/rejected: {len(used_images)}/{len(rejected_images)}")
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
