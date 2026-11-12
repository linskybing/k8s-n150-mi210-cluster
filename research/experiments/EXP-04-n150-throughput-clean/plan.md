---
artifact_type: experiment-plan
id: EXP-04-plan
version: 1
status: READY
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: [experiments/EXP-03-n150-batching/plan.md@1, integrity/gate4-2026-11-10.md@2]
source_files: [scripts/lc.sh, scripts/seq.sh, scripts/llm.yaml, scripts/llm-seq1.yaml, scripts/sglang-tt.yaml, scripts/sitecustomize.py]
verification_status: UNVERIFIED
produced_by: ai-draft
---

# EXP-04: EXP-03 without its confounds: do the vLLM vs SGLang throughput, TTFT and TPOT results hold with unique prompts and greedy sampling?
## Question and figure
- Kind: characterization (re-measurement). Gate 4 (integrity/gate4-2026-11-10.md, red-team F2, F3) found two confounds in EXP-03:
  seed = rep in every cell (repeated prompts hit the prefix cache, lowering TTFT) and unpinned sampling (server defaults differ).
- Claims (each rejected if the stated condition holds; written before the run):
  B1' vLLM max batch 32 / max batch 1 output tok/s at concurrency 8 >= 1.5x (rejected if < 1.5x);
  B2' both servers scale output tok/s from concurrency 1 to 8 by >= 1.5x (rejected if < 1.5x);
  T1  SGLang's lower TPOT at concurrency 1 (EXP-03: 23.6 vs 52.1 ms) persists: SGLang TPOT <= 0.75 x vLLM TPOT (rejected otherwise);
  P1  no prefix-cache reuse during the bench: SGLang log lines with #cached-token > 0 after the warmup = 0 and vLLM
      prefix_cache_hits_total stays at its post-warmup value (rejected otherwise; then the confound is not removed).
- Figure / table: replaces Fig. 2 and the 4.2 (3) table of the report; EXP-03 stays as the first round.
## Design (only what differs from EXP-03)
- Seed 10 x concurrency + rep (11-13, 81-83, 321-323): no prompt repeats across cells; warmup seed 0.
- `--temperature 0` (greedy) on every request.
- Same servers and matrix as EXP-03: vLLM max batch 32 and SGLang (sglang-tt.yaml) at concurrency 1/8/32, vLLM max batch 1 at
  1/8; 3 runs per cell on one fresh server instance each; /metrics captured after the bench.
## Statistics and validation
Environment-sensitive; mean and min-max of 3. Comparison with EXP-03 per cell reported as is (no pooling).
## Run procedure and preconditions
`setsid -f bash seq.sh bench-clean` on the node; n150 free; hf-token from .env temporarily in u-testuser, deleted after the run.
Re-pin (2026-11-10): gate4 v1 -> v2 only appends the post-EXP-04 addendum; F2/F3, which this plan answers, are unchanged.
## CHECKPOINT: EXPERIMENT_PLAN_READY
Decision (researcher, 2026-11-10, translated): EXP-03 re-run approved ("re-run (recommended)": distinct seed per cell, temperature
0, HF token temporarily in u-testuser and deleted afterwards).
## Addendum 2026-11-12: max batch 1 at concurrency 32
Researcher request (translated): "you should measure it" (the report's table showed "not measured" for this cell).
- Run: `setsid -f bash seq.sh seq1-c32` (n150 free at 05:34Z): one fresh load of llm-seq1.yaml (same manifest and spec as
  2026-11-10, sha checked), concurrency 32 with seeds 321-323 (the prompts of the vllm-a concurrency 32 cell) and concurrency 1
  with seeds 11-13 to compare days; num_prompts 2 x concurrency (64 and 8), temperature 0, 3 runs each.
- Raw: raw/vllm-b-1112 (bench), raw/vllm-b-1112-run (load and unload); summary row server vllm-b-1112.
- Written before the run: the concurrency 32 value is reported as measured. If concurrency 1 differs from 2026-11-10 (19.28 tok/s)
  by more than 5 %, the report gives both dates next to the cell.
