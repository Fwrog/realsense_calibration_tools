"""Marker-guided acquisition. Never writes calibration to device firmware."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import cv2
import numpy as np
import yaml

from .calibration import create_charuco_board, load_board_config, calibrate_color_camera_charuco
from .report import calibration_metrics, make_report, result_text, write_session_report
from .realsense_device import (
    load_camera_config, export_intrinsics, start_pipeline, stop_pipeline,
    color_frame_to_bgr, depth_frame_to_array,
)


def detect_board(image, board):
    corners, ids, markers, marker_ids = cv2.aruco.CharucoDetector(board).detectBoard(image)
    preview = image.copy()
    if marker_ids is not None:
        cv2.aruco.drawDetectedMarkers(preview, markers, marker_ids)
    if ids is not None:
        cv2.aruco.drawDetectedCornersCharuco(preview, corners, ids)
    return corners, ids, preview


def view_descriptor(corners, ids, board, image_size):
    """Project four board vertices to measure pose novelty independent of visible IDs."""
    if ids is None or len(ids) < 8 or board.checkCharucoCornersCollinear(ids):
        return None
    xy = board.getChessboardCorners()[ids.flatten(), :2]
    homography, _ = cv2.findHomography(xy, corners.reshape(-1, 2), 0)
    if homography is None:
        return None
    sx, sy = board.getChessboardSize()
    s = board.getSquareLength()
    vertices = np.float32([[[0, 0], [sx*s, 0], [sx*s, sy*s], [0, sy*s]]])
    projected = cv2.perspectiveTransform(vertices, homography)[0]
    result = projected / np.asarray(image_size)
    return result if np.isfinite(result).all() else None


def novel_view(descriptor, accepted, threshold=0.06):
    return descriptor is not None and all(
        np.sqrt(np.mean(np.sum((descriptor - old)**2, axis=1))) >= threshold
        for old in accepted
    )


def board_pose(corners, ids, board, intrinsics):
    """OpenCV PnP only for compatible distortion (or exactly zero coefficients)."""
    if ids is None or len(ids) < 8 or board.checkCharucoCornersCollinear(ids):
        return {"status": "insufficient_corners"}
    coeffs = np.asarray(intrinsics["coeffs"], dtype=float)
    if np.any(coeffs) and intrinsics["model"] != "distortion.brown_conrady":
        return {"status": "unsupported_factory_distortion", "model": intrinsics["model"]}
    k = np.array([[intrinsics["fx"], 0, intrinsics["ppx"]],
                  [0, intrinsics["fy"], intrinsics["ppy"]], [0, 0, 1]], dtype=float)
    objects = board.getChessboardCorners()[ids.flatten()]
    ok, rvec, tvec = cv2.solvePnP(objects, corners, k, coeffs)
    if not ok:
        return {"status": "pnp_failed"}
    rotation = cv2.Rodrigues(rvec)[0]
    camera_points = objects @ rotation.T + tvec.reshape(1, 3)
    if not np.isfinite(camera_points).all() or np.any(camera_points[:, 2] <= 0):
        return {"status": "invalid_pose"}
    projected, _ = cv2.projectPoints(objects, rvec, tvec, k, coeffs)
    rms = float(np.sqrt(np.mean(np.sum((projected.reshape(-1, 2)-corners.reshape(-1, 2))**2, axis=1))))
    transform = np.eye(4)
    transform[:3, :3], transform[:3, 3] = rotation, tvec.flatten()
    return {"status": "estimated_using_factory_intrinsics", "T_color_from_board": transform.tolist(),
            "translation_units": "m", "reprojection_rms_px": rms,
            "corner_z_m": camera_points[:, 2].tolist()}


def depth_consistency(corners, pose, depth, scale):
    """Local aligned-depth Z minus PnP Z; diagnostic, not a depth calibration."""
    residuals = []
    for (x, y), z in zip(corners.reshape(-1, 2), pose["corner_z_m"]):
        x, y = int(round(x)), int(round(y))
        patch = depth[max(0, y-2):y+3, max(0, x-2):x+3]
        valid = patch[patch > 0]
        if valid.size:
            residuals.append(float(np.median(valid)*scale-z))
    return {"valid_corners": len(residuals), "total_corners": len(corners),
            "median_depth_minus_pose_mm": float(np.median(residuals)*1000) if residuals else None,
            "median_absolute_difference_mm": float(np.median(np.abs(residuals))*1000) if residuals else None,
            "scope": "Single-view consistency only; affected by board size, pose, alignment and depth error."}


def run_session(args):
    config = load_camera_config(args.camera_config)
    board_config = load_board_config(args.board_config)
    board = create_charuco_board(board_config)
    session = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    session.mkdir(parents=True, exist_ok=False)
    image_dir = session / "images"
    image_dir.mkdir()
    board_path = session / "board.yaml"
    board_path.write_text(yaml.safe_dump(board_config), encoding="utf-8")
    summary = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(),
               "mode": args.mode, "status": "acquiring", "intrinsics_recalibrated": False,
               "firmware_modified": False, "board_config": board_config,
               "physical_size_confirmed": args.confirm_board_size,
               "accepted_views": 0, "capture_criteria": {"min_corners": 12, "min_board_roi_laplacian_variance": 30,
               "novelty_normalized_rms": 0.06, "stable_normalized_rms": 0.008},
               "warnings": ["Capture thresholds are heuristics, not accuracy certification."]}
    if not args.confirm_board_size:
        summary["warnings"].append("Board dimensions not confirmed for this physical print; metric pose is provisional.")
    accepted, records = [], []
    previous, stable_since, last_saved = None, None, -float("inf")
    best_count = -1
    try:
        export_intrinsics(session / "factory.json", config)
        factory = json.loads((session / "factory.json").read_text(encoding="utf-8"))
        handle = start_pipeline(config, align_depth=True)
        start = time.monotonic()
        try:
            for _ in range(int(config.get("warmup_frames", 30))):
                handle["pipeline"].wait_for_frames(10000)
            while time.monotonic() - start < args.seconds:
                frames = handle["aligner"].process(handle["pipeline"].wait_for_frames(10000))
                color, depth_frame = frames.get_color_frame(), frames.get_depth_frame()
                if not color or not depth_frame:
                    continue
                image = color_frame_to_bgr(handle["rs"], color)
                depth = depth_frame_to_array(depth_frame)
                corners, ids, preview = detect_board(image, board)
                count = 0 if ids is None else len(ids)
                descriptor = view_descriptor(corners, ids, board, (image.shape[1], image.shape[0]))
                now = time.monotonic()
                stable = descriptor is not None and previous is not None and np.sqrt(np.mean(np.sum((descriptor-previous)**2, axis=1))) < 0.008
                stable_since = (stable_since if stable_since is not None else now) if stable else None
                previous = descriptor
                sharpness = 0.0
                if count:
                    x, y, w, h = cv2.boundingRect(corners)
                    roi = cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
                    sharpness = float(cv2.Laplacian(roi, cv2.CV_64F).var())
                if count > best_count:
                    best_count = count
                    for filename, content in [("color.png", image), ("detection.png", preview)]:
                        if not cv2.imwrite(str(session / filename), content):
                            raise OSError(f"Failed to write {filename}")
                    np.save(session / "aligned_depth.npy", depth)
                    pose = board_pose(corners, ids, board, factory["streams"]["color"]["intrinsics"])
                    summary["best_corner_count"], summary["board_pose"] = count, pose
                    if "corner_z_m" in pose:
                        summary["depth_consistency"] = depth_consistency(corners, pose, depth, factory["streams"]["depth"]["depth_scale"])
                if args.mode == "auto" and count >= 12 and sharpness >= 30 and stable_since is not None and now-stable_since >= 0.5 and now-last_saved >= 1 and novel_view(descriptor, accepted):
                    name = f"view_{len(accepted):04d}.png"
                    if not cv2.imwrite(str(image_dir / name), image):
                        raise OSError(f"Failed to write {name}")
                    accepted.append(descriptor.copy())
                    records.append({"image": name, "corners": count, "sharpness": sharpness,
                                    "descriptor": descriptor.tolist(), "elapsed_s": now-start})
                    last_saved = now
                    print(f"Accepted {len(accepted)}/{args.views}: {count} corners", flush=True)
                if args.preview:
                    cv2.putText(preview, f"Corners {count} | Views {len(accepted)}/{args.views} | Move, then hold | Q stop",
                                (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                    cv2.imshow("RealSense automatic calibration", preview)
                    if cv2.waitKey(1) & 0xff in (ord('q'), 27):
                        break
                if args.mode == "auto" and len(accepted) >= args.views:
                    break
        finally:
            stop_pipeline(handle)
            if args.preview:
                cv2.destroyAllWindows()
        summary["status"] = "inspection_complete" if args.mode == "inspect" else "needs_more_views"
        if best_count < 8:
            summary["status"] = "needs_visible_board"
        if args.mode == "auto" and len(accepted) >= args.views:
            summary["status"] = "needs_board_size_confirmation"
            if args.confirm_board_size:
                summary["status"] = "calibrating"
                calibrate_color_camera_charuco(image_dir, board_path, session / "color_intrinsics.json",
                                               session / "detections", session / "undistortion",
                                               holdout_count=max(3, len(accepted)//5))
                fitted = json.loads((session / "color_intrinsics.json").read_text(encoding="utf-8"))
                summary["calibration_metrics"] = calibration_metrics(fitted)
                summary["status"] = "calibration_candidate_needs_validation"
                summary["intrinsics_recalibrated"] = True
                summary["warnings"].append("Reprojection error is not proof of improvement over factory intrinsics.")
    except KeyboardInterrupt:
        summary["status"] = "interrupted"
        raise
    except Exception as exc:
        summary["status"] = "calibration_failed" if summary["status"] == "calibrating" else "failed"
        summary["error"] = str(exc)
        raise
    finally:
        summary["accepted_views"] = len(accepted)
        (session / "capture.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        write_session_report(session, summary)
        print(result_text(summary), flush=True)
        print(f"Report: {(session / 'report.html').resolve()}", flush=True)
    return 0 if summary["status"] in {"inspection_complete", "calibration_candidate_needs_validation"} else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["inspect", "auto", "report"], default="inspect")
    parser.add_argument("--camera-config", type=Path, default=Path("configs/camera/d435i.yaml"))
    parser.add_argument("--board-config", type=Path, default=Path("configs/boards/charuco_A4_7x5_25mm.yaml"))
    parser.add_argument("--session", type=Path, help="Existing session directory for --mode report.")
    parser.add_argument("--output", type=Path, default=Path("outputs/sessions"))
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--views", type=int, default=25)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--confirm-board-size", action="store_true", help="Confirm this print matches the measured sizes in board YAML.")
    args = parser.parse_args()
    if args.mode == "report":
        if args.session is None:
            parser.error("--mode report requires --session.")
        _, report = make_report(args.session)
        print(f"Report: {report.resolve()}")
        return 0
    if args.session is not None:
        parser.error("--session is only used with --mode report.")
    if args.views < 15 or not np.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("Use --views >= 15 and finite --seconds > 0.")
    if args.confirm_board_size:
        board = load_board_config(args.board_config)
        if any(board.get(key) is None for key in ("square_size_mm_measured", "marker_size_mm_measured")):
            parser.error("Set measured square and marker dimensions before confirming.")
    return run_session(args)
