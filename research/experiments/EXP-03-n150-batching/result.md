---
artifact_type: experiment-result
id: EXP-03-result
version: 1
status: DRAFT
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: [experiments/EXP-03-n150-batching/plan.md@1]
source_files: [experiments/EXP-03-n150-batching/raw, scripts/lc.sh, scripts/analyze.py, experiments/EXP-03-n150-batching/plots/throughput.py]
verification_status: ANALYZED
produced_by: ai-draft
---

# EXP-03 result: output throughput vs concurrency on the n150, vLLM and SGLang
## Provenance
- Provided by: agent-run (`lc.sh bench`: `vllm bench serve` from the image, inside each server pod, backend openai, /v1/completions,
  random dataset, ISL 128, OSL 128, --ignore-eos, num-prompts max(8, 2 x concurrency), seed = rep, one discarded warmup).
- Servers: vLLM batch 32 = vllm-r3 of EXP-01 (03:38:26Z-03:45:57Z); vLLM batch 1 = llm-seq1.yaml (max_num_seqs 1, raw/vllm-b-run,
  03:54:37Z-04:05:00Z); SGLang batch 32 = sglang-tt-r3 of EXP-01 (04:27:28Z-04:32:20Z; max_running_requests 32).
- Raw: raw/{vllm-a,vllm-b,sglang}/c<C>-r<seed>.{json,log}. Processed: processed/throughput*.csv. Plot: plots/throughput.{pdf,png}
## Runs
24 runs, all completed (every request returned 128 tokens: analyze.py assert). Deviation from plan: the SGLang cell uses the fixed
manifest (EXP-01 Anomalies); the plan's SGLang = sglang-custom.yaml ran on CPU and was not benchmarked.
## Anomalies
- `error: timed out` printed once to seq.log during the SGLang bench (a kubectl exec message); all 9 SGLang result files are
  complete, each JSON date lies inside its own run window.
- SGLang concurrency 1, seed 1: 38.3 tok/s vs 44.4 and 44.7 for seeds 2-3 (first run after warmup); kept.
## Results
| ID | Finding | Value (mean, min-max, n=3) | Source |
|---|---|---|---|
| EXP-03#R1 | vLLM batch 32: output tok/s at concurrency 1 / 8 / 32 | 19.1 (19.0-19.3) / 113.2 (112.4-113.8) / 409.1 (403.4-414.8) | processed/throughput-summary.csv |
| EXP-03#R2 | vLLM batch 1: output tok/s at concurrency 1 / 8 | 19.5 (19.3-19.6) / 19.3 (19.1-19.4); TTFT at 8: 34,994 ms | same |
| EXP-03#R3 | batching at concurrency 8 (vLLM max batch 32 / max batch 1) | 5.9x (claim B1 holds, threshold 1.5x). Fixed 128-token outputs make a batch finish together, so this does not separate continuous from static batching | same |
| EXP-03#R4 | SGLang batch 32: output tok/s at concurrency 1 / 8 / 32 | 42.5 (38.3-44.7) / 217.7 (201.2-231.6) / 407.7 (401.4-410.8) | same |
| EXP-03#R5 | scaling 1 -> 8 | vLLM 5.9x, SGLang 5.1x (claim B2 holds) | same |
| EXP-03#R6 | TPOT at concurrency 1 / 8 / 32 | vLLM 52.1 / 68.5 / 69.7 ms; SGLang 23.6 / 35.6 / 73.2 ms | same |
| EXP-03#R7 | mean TTFT at concurrency 1 / 8 / 32 | vLLM 80 / 342 / 1151 ms; SGLang 36 / 196 / 744 ms | same |
## Statistics
3 runs per cell on one server instance (not independent replicates), mean and min-max. Client runs in the server pod (shares its
CPU; not controlled). Input is 127 tokens per prompt (--random-input-len 128; total_input_tokens / num_prompts = 127 in all 24 runs).
Confounds, reported in the report Sec. 4.2 (3): seed = rep in every cell, so prompts repeat across concurrency levels and hit the
prefix cache (SGLang r3 log: 23 of 81 prefill batches with #cached-token > 0; vLLM hits not captured), which lowers TTFT;
sampling not pinned (client temperature=None; server defaults vLLM temperature 0.6 top_p 0.9, SGLang also top_k 50).
## Validation
Same model code on both servers (tt_transformers, same KV size, trace on). Why vLLM's TPOT at concurrency 1 (52 ms) is 2.2x
SGLang's (24 ms) is not explained: HYPOTHESIS, vLLM's host-side sampling (`sample_on_device_mode=None`) or its per-step scheduler
overhead. vLLM max batch 1 decodes with shape [1, 1] yet has TPOT 51.2 ms, close to max batch 32 ([32, 1], 52.1 ms), so the
vLLM per-step time is mostly not device batch work; SGLang's warmup captures on-device sampling variants. Not tested. Not VALIDATED (no re-run on another day).
