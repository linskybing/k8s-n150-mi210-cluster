"""Fig. 6-1 (EXP-05): vLLM on the n150, one setting changed per server. Same workload as EXP-04 (127 in / 128 out, temperature 0).
Small multiples, one bar per setting: output throughput at concurrency 1, 8, 32 (each panel its own scale) and TPOT at concurrency 1.
Bars instead of lines because several settings have nearly equal values, which overlap as lines.
Run from the experiment directory: python3 plots/tuning.py -> plots/tuning.pdf (+ .png for the Markdown report)
Bars: mean of 3 runs, value printed; whiskers: min-max. Settings that did not load have no data and are left out."""
import csv
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path.home() / "Desktop/research/.agents/skills/systems-figures/scripts"))
from fig_check import check_layout

DATA = Path("processed/throughput.csv")  # columns: server,concurrency,rep,...,output_tok_s,mean_tpot_ms
OUT = Path("plots") / (Path(__file__).stem + ".pdf")
WIDTH_PT = 480
SERIES = (("vllm", "Baseline", "#1F3A5F"),
          ("vllm-b16", "Batch limit 16", "#6B7280"),
          ("vllm-sod", "On-device sampling", "#B45309"),
          ("vllm-notrace", "Trace off", "#9F1239"),
          ("vllm-len2k", "Context 2048", "#0F766E"))
PANELS = ((1, "output_tok_s", "Throughput, 1 request\n(tokens/s)"),
          (8, "output_tok_s", "Throughput, 8 requests\n(tokens/s)"),
          (32, "output_tok_s", "Throughput, 32 requests\n(tokens/s)"),
          (1, "mean_tpot_ms", "TPOT, 1 request\n(ms per token)"))

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
    "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42,
})

rows = list(csv.DictReader(DATA.open()))
present = [s for s in SERIES if any(r["server"] == s[0] for r in rows)]
fig, axes = plt.subplots(1, len(PANELS), sharey=True, figsize=(WIDTH_PT / 72, WIDTH_PT / 72 * 0.30))
ys = list(range(len(present)))[::-1]  # first setting on top

for ax, (c, col, label) in zip(axes, PANELS):
    top = 0
    for y, (key, _, color) in zip(ys, present):
        v = [float(r[col]) for r in rows if r["server"] == key and int(r["concurrency"]) == c]
        if not v:
            continue
        m = st.mean(v)
        ax.barh(y, m, xerr=[[m - min(v)], [max(v) - m]], color=color, height=0.65, error_kw={"elinewidth": 0.6})
        ax.text(max(v), y, f" {m:.1f}", va="center", fontsize=6)
        top = max(top, max(v))
    ax.set_xlim(0, top * 1.45)  # room for the value labels
    ax.set_xlabel(label)
    ax.tick_params(axis="y", length=0)
axes[0].set_yticks(ys)
axes[0].set_yticklabels([s[1] for s in present])
axes[0].set_ylabel("Setting")

fig.tight_layout(pad=0.3, w_pad=0.8)
check_layout(fig, OUT.stem)
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT)
fig.savefig(OUT.with_suffix(".png"), dpi=300)
