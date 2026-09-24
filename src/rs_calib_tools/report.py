"""One session summary, one report renderer. No camera or plotting dependency."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path


SCOPE = "Held-out poses are refitted per view. Pixel reprojection error is not metric depth accuracy."
NEXT_STEPS = {
    "inspection_complete": "Inspection only. Capture varied views to estimate color intrinsics.",
    "needs_more_views": "Capture more distinct positions, distances and tilts; hold each view still.",
    "needs_visible_board": "Bring the board into view and check the configured dictionary and dimensions.",
    "needs_board_size_confirmation": "Measure the printed board and confirm its dimensions before fitting.",
    "calibration_candidate_needs_validation": "Review held-out residuals, view coverage and parameter plausibility before use.",
    "failed": "Review the error below. Saved frames remain available.",
    "calibration_failed": "Review the fitting error. Saved frames remain available.",
    "interrupted": "Capture was interrupted. Saved frames remain available.",
}


def calibration_metrics(fitted):
    """Keep report metrics consistent with the fitting artifact."""
    return {key: fitted.get(key) for key in (
        "rms_reprojection_error_px", "heldout_mean_rms_px", "num_images_used",
        "heldout_views", "validation_scope")}


def _fmt(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "Not available" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)


def result_text(summary):
    metrics = summary.get("calibration_metrics", {})
    lines = [f"Status: {summary['status']}", f"Accepted views: {summary.get('accepted_views', 0)}"]
    if metrics:
        lines.append(f"Training RMS: {_fmt(metrics.get('rms_reprojection_error_px'))} px | "
                     f"Held-out mean RMS: {_fmt(metrics.get('heldout_mean_rms_px'))} px")
    lines.append(NEXT_STEPS.get(summary["status"], "See the report for session details."))
    return "\n".join(lines)


def write_session_report(session, summary):
    """Persist all evidence in JSON; present only the essential results in HTML."""
    session = Path(session)
    status = summary["status"]
    metrics = summary.get("calibration_metrics", {})
    views = metrics.get("heldout_views") or []
    rows = [("Accepted views", summary.get("accepted_views", 0)),
            ("Best detected corners", summary.get("best_corner_count")),
            ("Physical dimensions confirmed", summary.get("physical_size_confirmed", False))]
    if metrics:
        rows += [("Fitting / held-out views", f"{metrics.get('num_images_used', 0)} / {len(views)}"),
                 ("Training RMS (px)", metrics.get("rms_reprojection_error_px")),
                 ("Held-out mean RMS (px)", metrics.get("heldout_mean_rms_px"))]
        if metrics.get("heldout_factory_mean_rms_px") is not None:
            rows.append(("Factory held-out mean RMS (px)", metrics["heldout_factory_mean_rms_px"]))
    depth = summary.get("depth_consistency", {})
    if depth:
        rows.append(("Single-view depth / pose median absolute difference (mm)", depth.get("median_absolute_difference_mm")))
    table = "".join(f"<tr><th>{escape(label)}</th><td>{escape(_fmt(value))}</td></tr>" for label, value in rows)
    image = '<figure><img src="detection.png" alt="Detected ChArUco board"><figcaption>Actual session detection frame</figcaption></figure>' if (session / "detection.png").is_file() else ""
    warnings = list(summary.get("warnings", []))
    if summary.get("error"):
        warnings.insert(0, str(summary["error"]))
    notices = "".join(f"<li>{escape(str(item))}</li>" for item in warnings)
    comparison = ""
    if views:
        has_factory = any(v.get("factory_rms_px") is not None for v in views)
        scale = max([v["rms_px"] for v in views] + [v.get("factory_rms_px") or 0 for v in views]) or 1
        view_rows = []
        for view in views:
            cells = []
            for key, style in [("rms_px", "candidate")] + ([("factory_rms_px", "factory")] if has_factory else []):
                value = view.get(key)
                bar = f'<span class="bar {style}" style="width:{100*value/scale:.2f}%"></span>' if value is not None else ""
                cells.append(f'<td>{escape(_fmt(value))}<span class="track">{bar}</span></td>')
            name = str(view["path"]).replace("\\", "/").rsplit("/", 1)[-1]
            view_rows.append(f"<tr><th>{escape(name)}</th>{''.join(cells)}</tr>")
        factory_header = "<th>Factory (px)</th>" if has_factory else ""
        comparison = (f'<section><h2>Held-out reprojection</h2><p>Lower is better. Bars share a zero baseline and scale.</p>'
                      f'<table class="comparison"><thead><tr><th>View</th><th>Candidate (px)</th>{factory_header}</tr></thead>'
                      f"<tbody>{''.join(view_rows)}</tbody></table></section>")
    payload = json.dumps(summary, indent=2, allow_nan=False)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RealSense calibration report</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#182230;background:#f6f8fa;margin:0}}
main{{max-width:1000px;margin:auto;padding:32px 24px}}h1{{font-size:32px;line-height:1.2;margin:8px 0 16px}}
h2{{font-size:20px}}.label,figcaption{{font:13px ui-monospace,monospace;color:#475467}}
.status{{padding:12px 16px;border-left:4px solid #0072b2;background:#eaf4fb;overflow-wrap:anywhere}}
section{{margin:28px 0}}figure{{margin:24px 0}}img{{width:100%;max-height:380px;object-fit:contain;background:#182230}}
table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px 14px;border-bottom:1px solid #dce2e8;text-align:left;overflow-wrap:anywhere}}
th{{font-weight:500}}td{{font-variant-numeric:tabular-nums;white-space:nowrap}}.metrics th{{width:70%}}.comparison{{table-layout:fixed}}
.track{{display:block;height:6px;background:#edf1f5;margin-top:5px}}
.bar{{display:block;height:6px}}.candidate{{background:#0072b2}}.factory{{background:#98a2b3}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}a{{color:#0065a0}}summary{{cursor:pointer}}
footer{{border-top:1px solid #dce2e8;padding-top:16px;color:#475467;font-size:14px}}
@media(max-width:600px){{main{{padding:20px 12px}}h1{{font-size:26px}}th,td{{padding:8px}}}}
</style></head><body><main>
<div class="label">RealSense / Session report</div><h1>Calibration results</h1>
<p class="status">{escape(status.replace('_', ' ').capitalize())}</p><p>{escape(NEXT_STEPS.get(status, 'Review the session details below.'))}</p>
{image}<section><h2>At a glance</h2><table class="metrics">{table}</table></section>{comparison}
<section><h2>Interpretation</h2><p>{SCOPE}</p><p>Depth consistency is a single-view diagnostic, not a depth calibration.</p>
<ul>{notices}</ul></section>
<details><summary>Full session details</summary><pre>{escape(payload)}</pre></details>
<footer><a href="summary.json">Summary JSON</a> · Firmware modified: {escape(_fmt(summary.get('firmware_modified')))}
<br>Local report: review images and metadata before sharing.</footer></main></body></html>'''
    (session / "summary.json").write_text(payload, encoding="utf-8")
    (session / "report.html").write_text(html, encoding="utf-8")
    return session / "summary.json", session / "report.html"


def make_report(session):
    session = Path(session)
    summary = json.loads((session / "summary.json").read_text(encoding="utf-8"))
    return write_session_report(session, summary)


def main():
    parser = argparse.ArgumentParser(description="Rebuild a session report without camera access.")
    parser.add_argument("--session", required=True, type=Path)
    args = parser.parse_args()
    _, report = make_report(args.session)
    print(f"Report: {report.resolve()}")
    return 0
