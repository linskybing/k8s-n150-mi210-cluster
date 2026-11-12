"""Fig. 2 (EXP-04, unique prompts, temperature 0): output throughput vs concurrency on the n150, vLLM (max batch 32 and 1) and SGLang.
Run from the experiment directory: python3 plots/throughput.py -> plots/throughput.pdf (+ .png for the Markdown report)
Points: mean of 3 runs; whiskers: min-max; series offset slightly along x."""
import csv
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path.home() / "Desktop/research/.agents/skills/systems-figures/scripts"))
from fig_check import check_layout

DATA = Path("processed/throughput.csv")  # columns: server,concurrency,seed,...,output_tok_s
OUT = Path("plots") / (Path(__file__).stem + ".pdf")
ACCENT, MUTED, THIRD = "#1F3A5F", "#6B7280", "#B45309"
WIDTH_PT = 240
SERIES = (("vllm-a", "vLLM, batch 32", ACCENT, "s"),
          ("vllm-b", "vLLM, batch 1", MUTED, "o"),
          ("sglang", "SGLang, batch 32", THIRD, "^"))

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6.5,
    "axes.linewidth": 0.5, "lines.linewidth": 1.0, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "pdf.fonttype": 42,
})

rows = list(csv.DictReader(DATA.open()))
fig, ax = plt.subplots(figsize=(WIDTH_PT / 72, WIDTH_PT / 72 * 0.62))
xs = set()
DODGE = {"vllm-a": 0.94, "vllm-b": 1.0, "sglang": 1.06}  # small x offset per series so equal values do not overlap (caption says so)
for key, name, color, marker in SERIES:
    cs = sorted({int(r["concurrency"]) for r in rows if r["server"] == key})
    if not cs:
        continue
    v = [[float(r["output_tok_s"]) for r in rows if r["server"] == key and int(r["concurrency"]) == c] for c in cs]
    mean = [st.mean(x) for x in v]
    err = [[m - min(x) for m, x in zip(mean, v)], [max(x) - m for m, x in zip(mean, v)]]
    ax.errorbar([c * DODGE[key] for c in cs], mean, yerr=err, color=color, marker=marker, markersize=3, capsize=0, elinewidth=0.6, label=name)
    xs |= set(cs)
ax.set_xscale("log", base=2)
ax.set_xticks(sorted(xs))
ax.set_xticklabels([str(x) for x in sorted(xs)])
ax.minorticks_off()
ax.set_ylim(bottom=0)
ax.set_xlabel("Concurrent requests (log scale)")
ax.set_ylabel("Output throughput (tokens/s)")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, handletextpad=0.4, columnspacing=0.8)
fig.tight_layout(pad=0.2)
check_layout(fig, OUT.stem)
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT)
fig.savefig(OUT.with_suffix(".png"), dpi=300)
