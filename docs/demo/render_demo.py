"""Plot public demo metrics, never raw device data.

Visual contract: one-session comparison for the README, not a benchmark claim.
Left: mean per-view RMS. Right: all paired views, including the regression.
No uncertainty inferred. Gray = factory; blue = candidate. Source: adjacent JSON.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "d435i_charuco_results.json").read_text(encoding="utf-8-sig"))
views = data["per_view"]
factory = np.array([v["factory_rms_px"] for v in views])
candidate = np.array([v["candidate_rms_px"] for v in views])
assert np.isclose(factory.mean(), data["heldout_factory_mean_rms_px"])
assert np.isclose(candidate.mean(), data["heldout_candidate_mean_rms_px"])

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelcolor": "#344054", "text.color": "#182230"})
fig, (overview, detail) = plt.subplots(1, 2, figsize=(12, 5.1), gridspec_kw={"width_ratios": [1, 2.1]})
fig.subplots_adjust(left=.07, right=.98, bottom=.23, top=.70, wspace=.35)
fig.text(.07, .92, "RealSense calibration / Real-device demo", fontsize=21, weight="bold")
fig.text(.07, .845, "D435i  |  1280 × 720  |  25 captured views  |  20 fitting + 5 held out", color="#475467", fontsize=11)
colors = ["#98A2B3", "#0072B2"]
bars = overview.bar([0, 1], [factory.mean(), candidate.mean()], color=colors, width=.55)
overview.bar_label(bars, fmt="%.3f", padding=6, fontsize=13, weight="bold")
overview.set_xticks([0, 1], ["Factory", "Candidate"])
overview.set_ylim(0, .4)
overview.set_ylabel("Mean per-view RMS (px)")
overview.set_title("Held-out average", loc="left", pad=16, weight="bold")
x = np.arange(len(views))
for offset, values, color, label in [(-.18, factory, colors[0], "Factory"), (.18, candidate, colors[1], "Candidate")]:
    bars = detail.bar(x+offset, values, width=.34, color=color, label=label)
    detail.bar_label(bars, fmt="%.3f", padding=4, fontsize=9)
detail.set_xticks(x, [v["image"].removeprefix("view_").removesuffix(".png") for v in views])
detail.set_xlabel("Held-out view")
detail.set_ylabel("Reprojection RMS (px)")
detail.set_ylim(0, 1.05)
detail.set_title("Every held-out view", loc="left", pad=16, weight="bold")
detail.legend(frameon=False, loc="upper left", ncol=2, fontsize=10)
for ax in (overview, detail):
    ax.grid(axis="y", color="#EAECF0", linewidth=.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_color("#D0D5DD")
    ax.spines["bottom"].set_color("#D0D5DD")
fig.text(.07, .09, "Lower is better. Candidate improves 4/5 views; this is one session, not an accuracy certification.", fontsize=10)
fig.text(.07, .043, "Poses are refitted per held-out view. Pixel reprojection error is not metric depth accuracy.", fontsize=10, color="#475467")
fig.savefig(ROOT / "reprojection_comparison.png", dpi=160, facecolor="white")
plt.close(fig)
print("Rendered reprojection_comparison.png from public demo JSON.")
