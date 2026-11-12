---
artifact_type: experiment-plan
id: EXP-05-plan
version: 1
status: READY
created_at: 2026-11-11
updated_at: 2026-11-11
derived_from: [experiments/EXP-04-n150-throughput-clean/plan.md@1]
source_files: [scripts/lc.sh, scripts/seq.sh, scripts/llm.yaml, scripts/llm-cache.yaml, scripts/llama-3.2-1b-n150.json, scripts/llama-3.2-1b-n150-sod.json, scripts/llama-3.2-1b-n150-notrace.json, scripts/llama-3.2-1b-n150-b16.json, scripts/llama-3.2-1b-n150-len2k.json, scripts/llama-3.2-1b-n150-nowarm.json]
verification_status: UNVERIFIED
produced_by: ai-draft
---

# EXP-05: Which vLLM settings change throughput, latency and load time on the n150, and by how much?
## Question and figure
- Kind: characterization (one setting changed per server against a same-day baseline). Settings exist in tenstorrent/vllm
  222ee06 (`vllm/platforms/tt.py`, `vllm/v1/worker/tt_worker.py`, `tt_model_runner.py`) and tt-inference-server v0.11.1
  (`run_vllm_api_server.py`: `device_model_spec.vllm_args` become CLI flags; weights are downloaded only when
  `cache_root/weights/<model>` is empty).
- Claims (each rejected if the stated condition holds; written before the run):
  - B0 base reproduces EXP-04 vllm-a: output tok/s within 5 % in every cell (rejected otherwise; then EXP-05 is compared to its
    own base only).
  - S1 `sample_on_device_mode: all` cuts TPOT at concurrency 1 to <= 0.8 x base (rejected otherwise; tests the HYPOTHESIS in
    report v3 4.2 (3) that vLLM's ~52 ms TPOT comes from host-side sampling). A failed load is a result, not retried.
  - T1 `trace_mode: none` raises TPOT at concurrency 1 to >= 1.5 x base (rejected otherwise).
  - M1 `max_num_seqs 16` at concurrency 32 gives <= 0.6 x base output tok/s (rejected otherwise).
  - L1 `max_model_len 2048` cuts vLLM engine init (log `init engine ... took`) by >= 10 s; output tok/s within 5 % of base
    (rejected otherwise).
  - W1 `enable_model_warmup: false` cuts submit -> Ready by >= 30 s, and the first request (chat.py, marks chat-start ->
    chat-done) takes >= 10 x the same request on base (rejected otherwise).
  - C1 caches on a hostPath (llm-cache.yaml): the second load (r2) is Ready >= 60 s sooner than the first (r1, empty dir) and its
    log has no `Downloading weights` (rejected otherwise).
- Figure: `fig:tuning` -- per setting, output tok/s at concurrency 1/8/32 and TPOT at concurrency 1. Load times as a table.
## Design
- Workload as EXP-04: Llama-3.2-1B-Instruct, `vllm bench serve` in the server pod, random dataset, 127 input tokens
  (--random-input-len 128), 128 output tokens (--ignore-eos), seed 10 x concurrency + rep, --temperature 0, concurrency
  1/8/32 x 3 runs on one fresh server per setting, one discarded warmup (seed 0). nowarm and cache: load + query + unload only.
- Order: tune-base, tune-sod, tune-notrace, tune-b16, tune-len2k, tune-nowarm, cache (r1, r2). One `seq.sh` call per stage.
- Each setting must be visible in the server log (TTModelRunner line, non-default args); analyze.py asserts it.
## Statistics and validation
Environment-sensitive (shared node, other users' GPU jobs keep running); mean and min-max of 3; no pooling with EXP-04.
## Run procedure and preconditions
On the node in a new directory (`~/exp-n150-20261111/`, copy of research/scripts): n150 free (ClusterQueue
`tenstorrent.com/chip` 0); hf-token from .env created in u-testuser for the run and deleted afterwards; configmaps llm-spec*
and the hostPath dir /home/testuser/.cache/tt-vllm-cache deleted afterwards; cluster state captured before and after.
## CHECKPOINT: EXPERIMENT_PLAN_READY
Decision (researcher, 2026-11-11, translated): "新增調教實驗 (Recommended)" -- run new vLLM tuning experiments on the node
(~1.5-2 h of n150 time, HF token temporarily in u-testuser), plan approved in plan mode.
