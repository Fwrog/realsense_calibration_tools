# Local outputs

The main workflow creates `sessions/<timestamp>/` with raw captures, calibration results,
`summary.json` and a compact `report.html`. Reports use only their own session's results.

Generated outputs stay Git-ignored: they may contain device serial numbers, scene images
and machine-specific paths. Existing `calibration/` and `qc/` directories are retained as
historical or standalone-tool outputs, not mixed into new reports.
