---
artifact_type: experiment-result
id: EXP-04-result
version: 1
status: DRAFT
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: [experiments/EXP-04-n150-throughput-clean/plan.md@1]
source_files: [experiments/EXP-04-n150-throughput-clean/raw, scripts/lc.sh, scripts/seq.sh, scripts/analyze.py, experiments/EXP-04-n150-throughput-clean/plots/throughput.py]
verification_status: ANALYZED
produced_by: ai-draft
---

# EXP-04 result: EXP-03 re-measured with unique prompts and temperature 0
## Provenance
- Provided by: agent-run (`seq.sh bench-clean` on the node: `SEED_PER_CELL=1`, `BENCH_ARGS="--temperature 0"`; lc.sh as in
  research/scripts at the time of the run).
- Servers (one fresh load each): vLLM max batch 32 (llm.yaml, 12:34:51Z-12:45:57Z), SGLang (sglang-tt.yaml + sitecustomize.py,
  12:45:57Z-12:52:05Z), vLLM max batch 1 (llm-seq1.yaml, 12:52:05Z-13:06:06Z), 2026-11-10. hf-token (the .env TOKEN) existed in
  u-testuser 12:34:50Z-13:06:41Z and was deleted.
- Client: `vllm bench serve` in each server pod, random dataset, 127 input tokens (--random-input-len 128), 128 output tokens
  (--ignore-eos), seed 10 x concurrency + rep, --temperature 0, one discarded warmup (seed 0).
- Raw: raw/{vllm-a,vllm-b,sglang}/ (c<C>-r<rep>.json/log, warmup.log, metrics-after.txt), raw/*-run/ (load, logs, DRA, device-fds),
  raw/seq-bench-clean.log. Processed: processed/throughput*.csv. Plot: plots/throughput.{pdf,png}.
## Runs
24 bench runs, all completed with 128 output tokens per request (analyze.py asserts). device-fds.txt shows the card held by
VLLM::EngineCore (both vLLM servers) and sglang::scheduler.
## Anomalies
- Prefix-cache reuse is not zero (claim P1 as written is rejected): vLLM max batch 32 640 of 35,584 queried tokens, max batch 1
  448 of 10,624, SGLang 10 of 77 prefill batches with cached tokens. Each equals one 64-token block per run (10 runs incl. warmup;
  7 for max batch 1): `vllm bench serve` sends each run's first prompt once as an initial test request ("Starting initial single
  prompt test run", c*-r*.log), so that prompt repeats inside its own run. Repeats across cells are gone; the residue affects the
  first request of each run only.
## Results
| ID | Finding | Value (mean, min-max, n=3) | Source |
|---|---|---|---|
| EXP-04#R1 | vLLM max batch 32, output tok/s at concurrency 1 / 8 / 32 | 19.2 (19.0-19.3) / 112.7 (111.7-113.8) / 401.9 (399.9-403.9) | processed/throughput-summary.csv |
| EXP-04#R2 | vLLM max batch 1, concurrency 1 / 8 | 19.3 (19.1-19.5) / 19.4 (19.1-19.6); TTFT at 8: 34,701 ms | same |
| EXP-04#R3 | SGLang max batch 32, concurrency 1 / 8 / 32 | 39.4 (37.5-41.0) / 194.8 (185.6-209.7) / 403.7 (392.9-409.2) | same |
| EXP-04#R4 | B1' batching at concurrency 8 (max batch 32 / 1) | 5.8x (holds, threshold 1.5x) | same |
| EXP-04#R5 | B2' scaling 1 -> 8 | vLLM 5.9x, SGLang 4.9x (holds) | same |
| EXP-04#R6 | T1 TPOT at concurrency 1, SGLang / vLLM | 25.3 / 52.0 ms = 0.49 (holds, threshold 0.75) | same |
| EXP-04#R7 | TPOT at concurrency 8 / 32 | vLLM 68.9 / 71.4 ms; SGLang 39.9 / 74.3 ms | same |
| EXP-04#R8 | mean TTFT at concurrency 1 / 8 / 32 | vLLM 77 / 330 / 1119 ms; SGLang 37 / 201 / 711 ms | same |
| EXP-04#R9 | change vs EXP-03 (output tok/s) | vLLM within 2 % in every cell; SGLang -7.3 % (c1), -10.5 % (c8), -1.0 % (c32); mean TTFT changed by -4.4 % to +2.4 % (largest: SGLang c32 -4.4 %) | processed/ of EXP-03 and EXP-04 |
## Statistics
3 runs per cell on one server instance each; mean and min-max; no CI from n = 3.
## Validation
The EXP-03 confounds are removed except the tool's own test request (Anomalies). Removing them changed TTFT little, so they did not
drive EXP-03's TTFT comparison. Why SGLang is 7-10 % lower than in EXP-03 at concurrency 1 and 8 is not explained (greedy vs sampled
decoding, run-to-run variance): not tested. Not VALIDATED (no run on another day).
