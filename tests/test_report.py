import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from rs_calib_tools.automatic import main, run_session
from rs_calib_tools.report import calibration_metrics, make_report, result_text, write_session_report


class ReportTests(unittest.TestCase):
    def test_candidate_report_and_idempotent_rebuild(self):
        metrics = calibration_metrics({"rms_reprojection_error_px": .26, "heldout_mean_rms_px": .18,
                                       "num_images_used": 20, "heldout_views": [{"path": "view.png", "rms_px": .18}]})
        summary = {"status": "calibration_candidate_needs_validation", "accepted_views": 25,
                   "calibration_metrics": metrics, "warnings": ["<script>"], "firmware_modified": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_session_report(root, summary)
            html = (root / "report.html").read_text(encoding="utf-8")
            self.assertIn("0.180", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn("<details>", html)
            self.assertNotIn('<img src=', html)
            self.assertNotIn("Factory (px)", html)
            make_report(root)
            self.assertEqual(html, (root / "report.html").read_text(encoding="utf-8"))
            self.assertEqual(summary, json.loads((root / "summary.json").read_text()))
            self.assertLess(len(result_text(summary).splitlines()), 6)

    def test_factory_comparison_only_when_measured(self):
        summary = {"status": "calibration_candidate_needs_validation", "calibration_metrics": {
            "heldout_factory_mean_rms_px": .3,
            "heldout_views": [{"path": "v.png", "rms_px": .2, "factory_rms_px": .3}]}}
        with tempfile.TemporaryDirectory() as directory:
            write_session_report(Path(directory), summary)
            html = (Path(directory) / "report.html").read_text()
            self.assertIn("Factory (px)", html)
            self.assertIn("0.300", html)

    def test_report_mode_does_not_open_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_session_report(root, {"status": "needs_more_views"})
            with patch("sys.argv", ["rs-calib", "--mode", "report", "--session", directory]), \
                 patch("rs_calib_tools.automatic.start_pipeline") as camera, redirect_stdout(StringIO()):
                self.assertEqual(main(), 0)
                camera.assert_not_called()

    def test_missing_session_fails_without_creating_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                make_report(Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])


class CaptureFinalizationTests(unittest.TestCase):
    def test_failure_and_incomplete_paths_save_once_and_release_camera(self):
        config = {"dictionary": "DICT_5X5_100", "squares_x": 5, "squares_y": 7,
                  "square_size_mm_nominal": 24, "marker_size_mm_nominal": 12}
        for scenario in ("export_failure", "frame_failure", "interrupted", "empty_capture"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                args = argparse.Namespace(camera_config="unused", board_config="unused", output=root,
                                          confirm_board_size=True, mode="auto", seconds=1, views=15, preview=False)
                handle = {"pipeline": Mock()}
                if scenario == "frame_failure":
                    handle["pipeline"].wait_for_frames.side_effect = RuntimeError("frame read failed")
                elif scenario == "interrupted":
                    handle["pipeline"].wait_for_frames.side_effect = KeyboardInterrupt()

                def export(path, _):
                    if scenario == "export_failure":
                        raise RuntimeError("device missing")
                    Path(path).write_text("{}")

                with patch("rs_calib_tools.automatic.load_camera_config", return_value={"warmup_frames": 1 if scenario in ("frame_failure", "interrupted") else 0}), \
                     patch("rs_calib_tools.automatic.load_board_config", return_value=config), \
                     patch("rs_calib_tools.automatic.export_intrinsics", side_effect=export), \
                     patch("rs_calib_tools.automatic.start_pipeline", return_value=handle), \
                     patch("rs_calib_tools.automatic.stop_pipeline") as stop, \
                     patch("rs_calib_tools.automatic.time.monotonic", side_effect=[0, 2]), \
                     patch("rs_calib_tools.automatic.write_session_report", wraps=write_session_report) as report, \
                     redirect_stdout(StringIO()):
                    if scenario == "empty_capture":
                        self.assertEqual(run_session(args), 2)
                    else:
                        with self.assertRaises(KeyboardInterrupt if scenario == "interrupted" else RuntimeError):
                            run_session(args)
                    self.assertEqual(report.call_count, 1)
                    self.assertEqual(stop.call_count, 0 if scenario == "export_failure" else 1)
                session = next(root.iterdir())
                summary = json.loads((session / "summary.json").read_text())
                expected = "needs_visible_board" if scenario == "empty_capture" else "interrupted" if scenario == "interrupted" else "failed"
                self.assertEqual(summary["status"], expected)
                self.assertFalse(summary["intrinsics_recalibrated"])
                self.assertEqual(json.loads((session / "capture.json").read_text()), [])
