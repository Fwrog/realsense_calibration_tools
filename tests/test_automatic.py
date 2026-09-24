import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from rs_calib_tools.automatic import (
    board_pose, depth_consistency, detect_board, novel_view, view_descriptor,
)
from rs_calib_tools.report import write_session_report
from rs_calib_tools.calibration import create_charuco_board, calibrate_color_camera_charuco


CONFIG = {"dictionary": "DICT_5X5_100", "squares_x": 5, "squares_y": 7,
          "square_size_mm_nominal": 24, "marker_size_mm_nominal": 12}


class AutomaticTests(unittest.TestCase):
    def setUp(self):
        self.board = create_charuco_board(CONFIG)

    def test_generated_board_detects_all_corners(self):
        image = self.board.generateImage((600, 840), marginSize=30)
        corners, ids, _ = detect_board(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), self.board)
        self.assertEqual(len(ids), 24)
        descriptor = view_descriptor(corners, ids, self.board, (600, 840))
        self.assertTrue(novel_view(descriptor, []))
        self.assertFalse(novel_view(descriptor + 0.001, [descriptor]))
        self.assertTrue(novel_view(descriptor + 0.10, [descriptor]))

    def test_missing_corners_not_accepted(self):
        self.assertIsNone(view_descriptor(None, None, self.board, (640, 480)))
        self.assertFalse(novel_view(None, []))

    def test_invalid_board_dimensions(self):
        for size in [0, -1, 25, float('nan')]:
            with self.assertRaises(ValueError):
                create_charuco_board({**CONFIG, "marker_size_mm_nominal": size})

    def test_pose_direction_and_metric_units(self):
        ids = np.arange(24, dtype=np.int32).reshape(-1, 1)
        k = np.array([[900., 0, 640], [0, 900, 360], [0, 0, 1]])
        expected_t = np.array([-.06, -.08, .7])
        corners, _ = cv2.projectPoints(self.board.getChessboardCorners(), np.array([.1, -.2, .03]), expected_t, k, np.zeros(5))
        intrinsics = {"fx": 900, "fy": 900, "ppx": 640, "ppy": 360,
                      "coeffs": [0]*5, "model": "distortion.inverse_brown_conrady"}
        pose = board_pose(corners, ids, self.board, intrinsics)
        np.testing.assert_allclose(np.array(pose["T_color_from_board"])[:3, 3], expected_t, atol=1e-5)
        self.assertLess(pose["reprojection_rms_px"], .001)
        bad = board_pose(corners, ids, self.board, {**intrinsics, "coeffs": [.1, 0, 0, 0, 0]})
        self.assertEqual(bad["status"], "unsupported_factory_distortion")

    def test_depth_holes_and_units(self):
        depth = np.zeros((30, 30), dtype=np.uint16)
        corners = np.float32([[[5, 5]], [[20, 20]]])
        self.assertIsNone(depth_consistency(corners, {"corner_z_m": [.5, .5]}, depth, .001)["median_absolute_difference_mm"])
        depth[3:8, 3:8] = 501
        result = depth_consistency(corners, {"corner_z_m": [.5, .5]}, depth, .001)
        self.assertEqual(result["valid_corners"], 1)
        self.assertAlmostEqual(result["median_depth_minus_pose_mm"], 1)

    def test_report_preserves_incomplete_state_and_escapes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_session_report(root, {"status": "needs_more_views", "note": "<script>"})
            self.assertEqual(json.loads((root / "summary.json").read_text())["status"], "needs_more_views")
            self.assertIn("&lt;script&gt;", (root / "report.html").read_text())

    def test_mixed_resolutions_fail(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "board.yaml").write_text(yaml.safe_dump(CONFIG))
            cv2.imwrite(str(root / "a.png"), np.zeros((100, 100, 3), np.uint8))
            cv2.imwrite(str(root / "b.png"), np.zeros((200, 100, 3), np.uint8))
            with self.assertRaisesRegex(ValueError, "Mixed image resolutions"):
                calibrate_color_camera_charuco(root, root / "board.yaml", root / "result.json", root / "previews")

    def test_calibration_with_disjoint_holdout(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "board.yaml").write_text(yaml.safe_dump({**CONFIG, "board_id": "synthetic"}))
            pattern = self.board.generateImage((500, 700))
            vertices = np.float32([[0, 0, 0], [.12, 0, 0], [.12, .168, 0], [0, .168, 0]])
            pixels = np.float32([[0, 0], [499, 0], [499, 699], [0, 699]])
            k = np.array([[800., 0, 400], [0, 800, 300], [0, 0, 1]])
            for index in range(15):
                r = np.array([-.3+.15*(index%5), -.25+.25*(index//5), .02*index])
                t = np.array([-.08+.015*(index%5), -.10, .55+.02*(index//5)])
                target, _ = cv2.projectPoints(vertices, r, t, k, np.zeros(5))
                matrix = cv2.getPerspectiveTransform(pixels, target.reshape(-1, 2))
                image = cv2.warpPerspective(pattern, matrix, (800, 600), borderValue=255)
                cv2.imwrite(str(root / f"view_{index:02d}.png"), image)
            calibrate_color_camera_charuco(root, root / "board.yaml", root / "result.json", root / "previews", holdout_count=3)
            result = json.loads((root / "result.json").read_text())
            self.assertEqual(result["num_images_used"], 12)
            self.assertEqual(len(result["heldout_views"]), 3)
            self.assertFalse(set(result["used_images"]) & {v["path"] for v in result["heldout_views"]})
            self.assertLess(result["heldout_mean_rms_px"], 1)


if __name__ == "__main__":
    unittest.main()
