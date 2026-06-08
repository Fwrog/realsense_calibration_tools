from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from .alignment import make_depth_overlay


def load_camera_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def start_pipeline(
    camera_config: dict[str, Any],
    *,
    enable_color: bool = True,
    enable_depth: bool = True,
    align_depth: bool = False,
) -> dict[str, Any]:
    rs = _require_realsense()
    context = rs.context()
    if len(context.query_devices()) == 0:
        raise RuntimeError("No RealSense device detected. Check USB connection and RealSense Viewer first.")

    pipeline = rs.pipeline()
    rs_config = rs.config()
    fps = int(camera_config.get("fps", 30))

    if enable_depth:
        rs_config.enable_stream(
            rs.stream.depth,
            int(camera_config["depth_width"]),
            int(camera_config["depth_height"]),
            rs.format.z16,
            fps,
        )
    if enable_color:
        rs_config.enable_stream(
            rs.stream.color,
            int(camera_config["color_width"]),
            int(camera_config["color_height"]),
            rs.format.bgr8,
            fps,
        )

    profile = pipeline.start(rs_config)
    _apply_stable_sensor_options(rs, profile.get_device())
    aligner = rs.align(rs.stream.color) if align_depth else None
    return {"rs": rs, "pipeline": pipeline, "profile": profile, "aligner": aligner}


def stop_pipeline(pipeline_or_handle: Any) -> None:
    pipeline = pipeline_or_handle.get("pipeline") if isinstance(pipeline_or_handle, dict) else pipeline_or_handle
    if pipeline is not None:
        pipeline.stop()


def export_intrinsics(output_path: str | Path, camera_config: dict[str, Any]) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = start_pipeline(camera_config, enable_color=True, enable_depth=True)
    try:
        _warmup(handle, int(camera_config.get("warmup_frames", 30)))
        rs = handle["rs"]
        profile = handle["profile"]
        device = profile.get_device()

        color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        depth_sensor = device.first_depth_sensor()
        payload = {
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "camera_config": camera_config,
            "device": _device_info(rs, device),
            "streams": {
                "color": _stream_info(color_profile),
                "depth": {
                    **_stream_info(depth_profile),
                    "depth_scale": float(depth_sensor.get_depth_scale()),
                },
            },
            "extrinsics": {
                "depth_to_color": _extrinsics(depth_profile.get_extrinsics_to(color_profile)),
                "color_to_depth": _extrinsics(color_profile.get_extrinsics_to(depth_profile)),
            },
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output
    finally:
        stop_pipeline(handle)


def capture_color_images(output_dir: str | Path, camera_config: dict[str, Any]) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    handle = start_pipeline(camera_config, enable_color=True, enable_depth=False)
    saved = 0
    try:
        _warmup(handle, int(camera_config.get("warmup_frames", 30)))
        print("SPACE: save image | q/ESC: quit")
        while True:
            frames = handle["pipeline"].wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue
            color_bgr = color_frame_to_bgr(handle["rs"], color_frame)
            cv2.imshow("RealSense color calibration capture", color_bgr)
            key = cv2.waitKey(1) & 0xFF
            if key == 32:
                path = output / f"calib_{saved:04d}.png"
                cv2.imwrite(str(path), color_bgr)
                print(f"saved {path}")
                saved += 1
            elif key in (27, ord("q")):
                break
    finally:
        stop_pipeline(handle)
        cv2.destroyAllWindows()


def capture_aligned_rgbd_preview(output_dir: str | Path, camera_config: dict[str, Any]) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    handle = start_pipeline(camera_config, enable_color=True, enable_depth=True, align_depth=True)
    saved = 0
    try:
        _warmup(handle, int(camera_config.get("warmup_frames", 30)))
        print("SPACE: save color/depth/overlay | q/ESC: quit")
        print("Inspect object edges in the overlay for obvious depth-to-color misalignment; this is QC preview only.")
        while True:
            frames = handle["pipeline"].wait_for_frames()
            frames = handle["aligner"].process(frames)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            color_bgr = color_frame_to_bgr(handle["rs"], color_frame)
            depth_raw = depth_frame_to_array(depth_frame)
            overlay = make_depth_overlay(color_bgr, depth_raw)
            cv2.imshow("RealSense RGB-D alignment QC", overlay)
            key = cv2.waitKey(1) & 0xFF
            if key == 32:
                cv2.imwrite(str(output / f"color_{saved:04d}.png"), color_bgr)
                cv2.imwrite(str(output / f"depth_overlay_{saved:04d}.png"), overlay)
                np.save(output / f"aligned_depth_{saved:04d}.npy", depth_raw)
                print(f"saved RGB-D preview {saved:04d}")
                saved += 1
            elif key in (27, ord("q")):
                break
    finally:
        stop_pipeline(handle)
        cv2.destroyAllWindows()


def color_frame_to_bgr(rs: Any, color_frame: Any) -> np.ndarray:
    data = np.asanyarray(color_frame.get_data())
    frame_format = color_frame.profile.format()
    if frame_format == rs.format.bgr8:
        return data.copy()
    if frame_format == rs.format.rgb8:
        return cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
    if frame_format == rs.format.yuyv:
        return cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
    raise RuntimeError(f"Unsupported RealSense color format: {frame_format}")


def depth_frame_to_array(depth_frame: Any) -> np.ndarray:
    return np.asanyarray(depth_frame.get_data()).copy()


def _require_realsense() -> Any:
    try:
        import pyrealsense2 as rs
    except ImportError as exc:
        raise RuntimeError(
            "pyrealsense2 is not installed. Install the rs_calib environment or the Intel RealSense SDK Python bindings."
        ) from exc
    return rs


def _warmup(handle: dict[str, Any], frame_count: int) -> None:
    for _ in range(max(0, frame_count)):
        handle["pipeline"].wait_for_frames()


def _apply_stable_sensor_options(rs: Any, device: Any) -> None:
    for sensor in device.query_sensors():
        name = _safe_sensor_name(rs, sensor).lower()
        _set_option_if_supported(rs, sensor, rs.option.frames_queue_size, 16.0)
        if hasattr(rs.option, "global_time_enabled"):
            _set_option_if_supported(rs, sensor, rs.option.global_time_enabled, 1.0)
        if "rgb" in name:
            _set_option_if_supported(rs, sensor, rs.option.enable_auto_exposure, 1.0)
            if hasattr(rs.option, "auto_exposure_priority"):
                _set_option_if_supported(rs, sensor, rs.option.auto_exposure_priority, 0.0)
        elif "stereo" in name:
            _set_option_if_supported(rs, sensor, rs.option.enable_auto_exposure, 1.0)


def _set_option_if_supported(rs: Any, sensor: Any, option: Any, value: float) -> None:
    try:
        if sensor.supports(option):
            sensor.set_option(option, value)
    except Exception:
        # Sensor options vary by firmware and stream state; failures should not
        # block the minimal capture flow.
        return


def _safe_sensor_name(rs: Any, sensor: Any) -> str:
    try:
        return sensor.get_info(rs.camera_info.name)
    except Exception:
        return "unknown_sensor"


def _device_info(rs: Any, device: Any) -> dict[str, Any]:
    fields = {
        "name": rs.camera_info.name,
        "serial_number": rs.camera_info.serial_number,
        "firmware_version": rs.camera_info.firmware_version,
        "physical_port": rs.camera_info.physical_port,
        "product_id": rs.camera_info.product_id,
        "product_line": rs.camera_info.product_line,
    }
    info = {key: _safe_device_info(device, value) for key, value in fields.items()}
    info["sdk_version"] = getattr(rs, "__version__", "unknown")
    return info


def _safe_device_info(device: Any, info_key: Any) -> str | None:
    try:
        if device.supports(info_key):
            return str(device.get_info(info_key))
    except Exception:
        return None
    return None


def _stream_info(profile: Any) -> dict[str, Any]:
    intrinsics = profile.get_intrinsics()
    return {
        "stream": str(profile.stream_type()),
        "format": str(profile.format()),
        "width": int(profile.width()),
        "height": int(profile.height()),
        "fps": int(profile.fps()),
        "intrinsics": {
            "width": int(intrinsics.width),
            "height": int(intrinsics.height),
            "fx": float(intrinsics.fx),
            "fy": float(intrinsics.fy),
            "ppx": float(intrinsics.ppx),
            "ppy": float(intrinsics.ppy),
            "model": str(intrinsics.model),
            "coeffs": [float(value) for value in intrinsics.coeffs],
        },
    }


def _extrinsics(extrinsics: Any) -> dict[str, list[float]]:
    return {
        "rotation": [float(value) for value in extrinsics.rotation],
        "translation": [float(value) for value in extrinsics.translation],
    }
