from __future__ import annotations

import cv2
import numpy as np


def depth_to_colormap(depth_raw: np.ndarray, max_depth_mm: int = 4000) -> np.ndarray:
    if depth_raw.size == 0:
        raise ValueError("depth_raw is empty")
    clipped = np.clip(depth_raw, 0, max_depth_mm).astype(np.float32)
    scaled = cv2.convertScaleAbs(clipped, alpha=255.0 / max_depth_mm)
    return cv2.applyColorMap(scaled, cv2.COLORMAP_JET)


def make_depth_overlay(color_bgr: np.ndarray, aligned_depth_raw: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    if color_bgr.size == 0:
        raise ValueError("color_bgr is empty")
    if aligned_depth_raw.size == 0:
        raise ValueError("aligned_depth_raw is empty")

    depth_color = depth_to_colormap(aligned_depth_raw)
    if depth_color.shape[:2] != color_bgr.shape[:2]:
        depth_color = cv2.resize(depth_color, (color_bgr.shape[1], color_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

    valid_mask = aligned_depth_raw > 0
    if valid_mask.shape[:2] != color_bgr.shape[:2]:
        valid_mask = cv2.resize(valid_mask.astype("uint8"), (color_bgr.shape[1], color_bgr.shape[0]), interpolation=cv2.INTER_NEAREST) > 0

    overlay = color_bgr.copy()
    blended = cv2.addWeighted(color_bgr, 1.0 - alpha, depth_color, alpha, 0.0)
    overlay[valid_mask] = blended[valid_mask]
    return overlay

